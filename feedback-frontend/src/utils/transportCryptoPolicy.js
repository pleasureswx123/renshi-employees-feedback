import axios from 'axios'

import { getSessionJson, removeSessionItem, setSessionJson } from './sessionCache'

const API_BASE_URL = import.meta.env.VITE_APP_BASE_API
const CONFIG_URL = '/transport/crypto/frontend-config'
const CACHE_KEY = 'feedbackTransportCryptoPolicy'
const FALLBACK_TTL_SECONDS = 60
const DEFAULT_VERSION = '1'
const DEFAULT_REQUEST_ALGORITHM = 'RSA_OAEP_AES_256_GCM'
const DEFAULT_RESPONSE_ALGORITHM = 'AES_256_GCM'
const EXCLUDED_PATHS = [
  CONFIG_URL,
  '/transport/crypto/public-key',
  '/common/download',
  '/common/download/resource',
  '/common/files',
  '/system/file/download'
]

const policyClient = axios.create({ baseURL: API_BASE_URL, timeout: 10000 })
let cachedPolicy = null
let inflightPolicy = null

function now() {
  return Math.floor(Date.now() / 1000)
}

function normalizePaths(paths) {
  return Array.isArray(paths) ? paths.map(path => String(path || '').trim()).filter(Boolean) : []
}

function normalizePolicy(payload = {}) {
  const expireAt = Number(payload.configExpireAt || 0)
  return {
    transportCryptoActive: Boolean(payload.transportCryptoActive),
    transportCryptoEnabled: Boolean(payload.transportCryptoEnabled),
    transportCryptoMode: String(payload.transportCryptoMode || 'off'),
    envelopeVersion: String(payload.envelopeVersion || DEFAULT_VERSION),
    publicKeyUrl: String(payload.publicKeyUrl || '/transport/crypto/public-key'),
    requestEnvelopeAlgorithm: String(payload.requestEnvelopeAlgorithm || DEFAULT_REQUEST_ALGORITHM),
    responseEnvelopeAlgorithm: String(payload.responseEnvelopeAlgorithm || DEFAULT_RESPONSE_ALGORITHM),
    enabledPaths: normalizePaths(payload.enabledPaths),
    requiredPaths: normalizePaths(payload.requiredPaths),
    excludePaths: normalizePaths(payload.excludePaths),
    maxEncryptedGetUrlLength: Number(payload.maxEncryptedGetUrlLength || 4096),
    configExpireAt: expireAt,
    retryAt: Number(payload.retryAt || expireAt || now() + FALLBACK_TTL_SECONDS)
  }
}

function fallbackPolicy() {
  return normalizePolicy({
    transportCryptoActive: false,
    excludePaths: EXCLUDED_PATHS,
    retryAt: now() + FALLBACK_TTL_SECONDS
  })
}

function isUsable(policy) {
  return Boolean(policy?.publicKeyUrl && Number(policy.retryAt) > now())
}

function pathMatches(path, patterns) {
  return patterns.some(pattern => path === pattern || path.startsWith(`${pattern}/`))
}

function baseApiPath() {
  if (!API_BASE_URL) return ''
  if (/^https?:\/\//.test(API_BASE_URL)) {
    const path = new URL(API_BASE_URL).pathname
    return path === '/' ? '' : path
  }
  return API_BASE_URL
}

export function getRequestPath(url = '') {
  const normalizedUrl = String(url || '')
  let path = /^https?:\/\//.test(normalizedUrl)
    ? new URL(normalizedUrl).pathname
    : normalizedUrl.split('?')[0] || '/'
  const prefix = baseApiPath()
  if (prefix && path.startsWith(prefix)) {
    path = path.slice(prefix.length) || '/'
  }
  return path
}

export function getTransportCryptoPolicy() {
  return cachedPolicy || fallbackPolicy()
}

export function invalidateTransportCryptoPolicy() {
  cachedPolicy = null
  inflightPolicy = null
  removeSessionItem(CACHE_KEY)
}

export async function ensureTransportCryptoPolicyLoaded(forceRefresh = false) {
  if (!forceRefresh && !cachedPolicy) {
    const persistedValue = getSessionJson(CACHE_KEY)
    const persisted = persistedValue ? normalizePolicy(persistedValue) : null
    if (isUsable(persisted)) cachedPolicy = persisted
  }
  if (!forceRefresh && isUsable(cachedPolicy)) return cachedPolicy
  if (inflightPolicy) return inflightPolicy

  inflightPolicy = policyClient
    .get(CONFIG_URL)
    .then(response => {
      cachedPolicy = normalizePolicy(response?.data?.data)
      setSessionJson(CACHE_KEY, cachedPolicy)
      return cachedPolicy
    })
    .catch(error => {
      const stalePolicy = cachedPolicy || getSessionJson(CACHE_KEY)
      cachedPolicy = stalePolicy
        ? normalizePolicy({ ...stalePolicy, retryAt: now() + FALLBACK_TTL_SECONDS })
        : fallbackPolicy()
      setSessionJson(CACHE_KEY, cachedPolicy)
      console.warn('加载传输加密策略失败，将按后端最终策略处理请求', error)
      return cachedPolicy
    })
    .finally(() => {
      inflightPolicy = null
    })
  return inflightPolicy
}

export function shouldEncryptRequest(config, policy = getTransportCryptoPolicy()) {
  if (!policy.transportCryptoActive) return false
  const path = getRequestPath(config.url)
  const exclusions = [...EXCLUDED_PATHS, ...(policy.excludePaths || [])]
  if (pathMatches(path, exclusions)) return false
  if (policy.enabledPaths?.length && !pathMatches(path, policy.enabledPaths)) return false
  if (config.headers?.encrypt === false) return false
  if (['blob', 'arraybuffer'].includes(config.responseType)) return false
  const contentType = String(config.headers?.['Content-Type'] || config.headers?.get?.('Content-Type') || '')
  return !contentType.includes('multipart/form-data')
}

export function shouldEncryptQuery(config, policy = getTransportCryptoPolicy()) {
  return config.headers?.encryptQuery !== false && shouldEncryptRequest(config, policy)
}

export function shouldDecryptResponse(config, policy = getTransportCryptoPolicy()) {
  if (config.headers?.encryptResponse === false) return false
  if (['blob', 'arraybuffer'].includes(config.responseType)) return false
  if (config.__transportCryptoEnabledForRequest !== undefined) {
    return config.__transportCryptoEnabledForRequest
  }
  return shouldEncryptRequest(config, policy)
}
