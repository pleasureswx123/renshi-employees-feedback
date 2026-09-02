import axios from 'axios'

import {
  ensureTransportCryptoPolicyLoaded,
  getRequestPath,
  getTransportCryptoPolicy,
  shouldDecryptResponse,
  shouldEncryptQuery,
  shouldEncryptRequest
} from './transportCryptoPolicy'

const API_BASE_URL = import.meta.env.VITE_APP_BASE_API
const ENABLE_HEADER = 'X-Transport-Encrypt'
const KEY_ID_HEADER = 'X-Key-Id'
const RESPONSE_ENCRYPTED_HEADER = 'x-body-encrypted'
const RETRYABLE_MESSAGES = new Set(['Decryption failed', '密钥版本不存在'])
const keyClient = axios.create({ baseURL: API_BASE_URL, timeout: 10000 })

let cachedKey = null
let inflightKey = null

function browserCrypto() {
  if (!globalThis.crypto?.subtle) throw new Error('当前浏览器不支持 Web Crypto API')
  return globalThis.crypto
}

function headerValue(headers, name) {
  if (!headers) return undefined
  return typeof headers.get === 'function' ? headers.get(name) : headers[name] ?? headers[name.toLowerCase()]
}

function setHeader(headers, name, value) {
  if (typeof headers?.set === 'function') headers.set(name, value)
  else if (headers) headers[name] = value
}

function toBase64Url(bytes) {
  let binary = ''
  bytes.forEach(byte => {
    binary += String.fromCharCode(byte)
  })
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '')
}

function fromBase64Url(value) {
  const normalized = String(value).replace(/-/g, '+').replace(/_/g, '/')
  const padded = normalized + '='.repeat((4 - (normalized.length % 4 || 4)) % 4)
  return Uint8Array.from(atob(padded), char => char.charCodeAt(0))
}

function pemToBuffer(pem) {
  const normalized = pem
    .replace(/-----BEGIN PUBLIC KEY-----/g, '')
    .replace(/-----END PUBLIC KEY-----/g, '')
    .replace(/\s+/g, '')
  return Uint8Array.from(atob(normalized), char => char.charCodeAt(0)).buffer
}

function clone(value) {
  if (value === undefined || value === null) return value
  if (typeof structuredClone === 'function') return structuredClone(value)
  return typeof value === 'object' ? JSON.parse(JSON.stringify(value)) : value
}

function requestAad(config) {
  return {
    method: String(config.method || 'get').toUpperCase(),
    path: getRequestPath(config.url)
  }
}

function responseAad(config) {
  return { ...requestAad(config), direction: 'response' }
}

function rememberOriginal(config) {
  if (config.__transportOriginalSnapshot) return
  config.__transportOriginalSnapshot = {
    url: config.url,
    params: clone(config.params),
    data: clone(config.data),
    contentType: headerValue(config.headers, 'Content-Type')
  }
}

function now() {
  return Math.floor(Date.now() / 1000)
}

function keyUsable(key) {
  return Boolean(key?.kid && key?.publicKey && Number(key.expireAt) > now() + 30)
}

async function getPublicKey() {
  if (keyUsable(cachedKey)) return cachedKey
  if (inflightKey) return inflightKey
  const policy = await ensureTransportCryptoPolicyLoaded()
  inflightKey = keyClient
    .get(policy.publicKeyUrl)
    .then(async response => {
      const payload = response?.data?.data
      if (response?.data?.code !== 200 || !payload?.kid || !payload?.publicKey) {
        throw new Error(response?.data?.msg || '获取传输层公钥失败')
      }
      if (String(payload.envelopeVersion || '1') !== policy.envelopeVersion) {
        throw new Error('传输层公钥协议版本不受支持')
      }
      if (payload.alg !== policy.requestEnvelopeAlgorithm) {
        throw new Error('传输层公钥算法不受支持')
      }
      const publicKey = await browserCrypto().subtle.importKey(
        'spki',
        pemToBuffer(payload.publicKey),
        { name: 'RSA-OAEP', hash: 'SHA-256' },
        false,
        ['encrypt']
      )
      cachedKey = { ...payload, publicKey }
      return cachedKey
    })
    .finally(() => {
      inflightKey = null
    })
  return inflightKey
}

async function createContext() {
  const crypto = browserCrypto()
  const key = await getPublicKey()
  const aesKey = await crypto.subtle.generateKey({ name: 'AES-GCM', length: 256 }, true, [
    'encrypt',
    'decrypt'
  ])
  const rawKey = await crypto.subtle.exportKey('raw', aesKey)
  const encryptedKey = await crypto.subtle.encrypt({ name: 'RSA-OAEP' }, key.publicKey, rawKey)
  return {
    kid: key.kid,
    alg: key.alg,
    envelopeVersion: String(key.envelopeVersion || '1'),
    aesKey,
    ek: toBase64Url(new Uint8Array(encryptedKey))
  }
}

async function encryptText(context, plainText, aad) {
  const crypto = browserCrypto()
  const iv = crypto.getRandomValues(new Uint8Array(12))
  const ciphertext = await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv, additionalData: new TextEncoder().encode(JSON.stringify(aad)) },
    context.aesKey,
    new TextEncoder().encode(plainText)
  )
  return {
    v: context.envelopeVersion,
    kid: context.kid,
    alg: context.alg,
    ts: now(),
    nonce: crypto.randomUUID(),
    ek: context.ek,
    aad,
    iv: toBase64Url(iv),
    ct: toBase64Url(new Uint8Array(ciphertext))
  }
}

async function decryptEnvelope(envelope, context) {
  const plaintext = await browserCrypto().subtle.decrypt(
    {
      name: 'AES-GCM',
      iv: fromBase64Url(envelope.iv),
      additionalData: new TextEncoder().encode(JSON.stringify(envelope.aad || {}))
    },
    context.aesKey,
    fromBase64Url(envelope.ct)
  )
  return new TextDecoder().decode(plaintext)
}

function queryEnvelope(envelope) {
  return toBase64Url(new TextEncoder().encode(JSON.stringify(envelope)))
}

function formEnvelope(envelope) {
  const form = new URLSearchParams()
  Object.entries(envelope).forEach(([key, value]) => {
    form.set(key, typeof value === 'object' ? JSON.stringify(value) : String(value))
  })
  return form.toString()
}

export async function encryptTransportRequest(config) {
  const policy = await ensureTransportCryptoPolicyLoaded()
  if (!shouldEncryptRequest(config, policy)) {
    config.__transportCryptoEnabledForRequest = false
    return config
  }

  rememberOriginal(config)
  const context = await createContext()
  const method = String(config.method || 'get').toLowerCase()
  const aad = requestAad(config)

  if (shouldEncryptQuery(config, policy) && (config.params || ['get', 'delete'].includes(method))) {
    const envelope = await encryptText(context, JSON.stringify(config.params || {}), aad)
    config.params = { __enc: queryEnvelope(envelope) }
    const queryLength = `${config.url}?${new URLSearchParams(config.params)}`.length
    if (queryLength > policy.maxEncryptedGetUrlLength) {
      throw new Error('当前GET/DELETE请求参数加密后长度超限，请改用POST请求或精简查询条件')
    }
  }

  if (['post', 'put', 'patch', 'delete'].includes(method)) {
    const envelope = await encryptText(context, JSON.stringify(config.data ?? {}), aad)
    const contentType = String(headerValue(config.headers, 'Content-Type') || '').toLowerCase()
    if (contentType.includes('application/x-www-form-urlencoded')) {
      config.data = formEnvelope(envelope)
    } else {
      config.data = envelope
      setHeader(config.headers, 'Content-Type', 'application/json;charset=utf-8')
    }
  }

  setHeader(config.headers, ENABLE_HEADER, '1')
  setHeader(config.headers, KEY_ID_HEADER, context.kid)
  config.__transportCryptoContext = context
  config.__transportCryptoEnabledForRequest = true
  return config
}

export function invalidateTransportKeyMeta() {
  cachedKey = null
  inflightKey = null
}

export function resetTransportRequestConfig(config) {
  const snapshot = config?.__transportOriginalSnapshot
  if (!snapshot) return config
  config.url = snapshot.url
  config.params = clone(snapshot.params)
  config.data = clone(snapshot.data)
  if (snapshot.contentType) setHeader(config.headers, 'Content-Type', snapshot.contentType)
  delete config.__transportCryptoContext
  delete config.__transportCryptoEnabledForRequest
  return config
}

export function shouldRetryTransportWithFreshKey(error) {
  return RETRYABLE_MESSAGES.has(error?.message) || RETRYABLE_MESSAGES.has(error?.response?.data?.msg)
}

function validateResponseEnvelope(envelope, response, context, policy) {
  const expectedAad = responseAad(response.config)
  const responseKid = headerValue(response.headers, KEY_ID_HEADER)
  if (String(envelope?.v || '') !== policy.envelopeVersion) throw new Error('响应协议版本不受支持')
  if (String(envelope?.alg || '') !== policy.responseEnvelopeAlgorithm) throw new Error('响应算法不受支持')
  if (String(envelope?.kid || '') !== String(context.kid)) throw new Error('响应密钥版本不匹配')
  if (responseKid && String(responseKid) !== String(envelope.kid)) throw new Error('响应密钥标识不一致')
  if (
    envelope?.aad?.method !== expectedAad.method ||
    envelope?.aad?.path !== expectedAad.path ||
    envelope?.aad?.direction !== 'response'
  ) {
    throw new Error('传输层响应AAD不合法')
  }
}

export async function decryptTransportResponse(response) {
  if (headerValue(response.headers, RESPONSE_ENCRYPTED_HEADER) !== '1') return response
  if (!shouldDecryptResponse(response.config, getTransportCryptoPolicy())) return response
  const context = response.config.__transportCryptoContext
  if (!context) throw new Error('缺少响应解密上下文')
  const envelope = typeof response.data === 'string' ? JSON.parse(response.data) : response.data
  validateResponseEnvelope(envelope, response, context, getTransportCryptoPolicy())
  response.data = JSON.parse(await decryptEnvelope(envelope, context))
  return response
}

export async function decryptTransportErrorResponse(error) {
  if (!error?.response) return error
  try {
    error.response = await decryptTransportResponse(error.response)
  } catch (decryptError) {
    console.error('解密错误响应失败', decryptError)
  }
  return error
}
