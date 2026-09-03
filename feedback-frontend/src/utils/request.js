import axios from 'axios'
import { ElMessage } from 'element-plus'

import { getToken, removeToken } from './auth'
import {
  decryptTransportErrorResponse,
  decryptTransportResponse,
  encryptTransportRequest,
  invalidateTransportKeyMeta,
  resetTransportRequestConfig,
  shouldRetryTransportWithFreshKey
} from './transportCrypto'

const recentMutations = new Map()
let unauthorizedHandler = null
let unauthorizedTask = null

function createRequestError(message, { kind, requestSent, status = 0, data, cause } = {}) {
  const error = new Error(message || '请求失败', cause ? { cause } : undefined)
  error.kind = kind || 'UNKNOWN'
  error.requestSent = Boolean(requestSent)
  error.status = Number(status || 0)
  error.data = data
  error.__requestClassified = true
  return error
}

function shouldShowError(config, error) {
  return !config?.suppressErrorMessage && !error?.suppressErrorMessage
}

function wrapRequestAdapter(config) {
  if (config.__requestAdapterWrapped) return config
  const adapter = axios.getAdapter(config.adapter)
  config.adapter = adapterConfig => {
    adapterConfig.__requestSent = true
    return adapter(adapterConfig)
  }
  config.__requestAdapterWrapped = true
  return config
}

export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = handler
}

async function handleUnauthorized() {
  removeToken()
  if (!unauthorizedTask && unauthorizedHandler) {
    unauthorizedTask = Promise.resolve(unauthorizedHandler()).finally(() => {
      unauthorizedTask = null
    })
  }
  await unauthorizedTask
}

function checkDuplicateMutation(config) {
  const method = String(config.method || 'get').toLowerCase()
  if (!['post', 'put', 'patch'].includes(method) || config.headers?.repeatSubmit === false) return null
  const fingerprint = `${method}:${config.url}:${JSON.stringify(config.data ?? null)}`
  const currentTime = Date.now()
  const interval = Number(config.headers?.repeatInterval || 1000)
  if (currentTime - Number(recentMutations.get(fingerprint) || 0) < interval) {
    throw createRequestError('请求正在处理中，请勿重复提交', {
      kind: 'DUPLICATE_MUTATION',
      requestSent: false
    })
  }
  recentMutations.set(fingerprint, currentTime)
  return fingerprint
}

const service = axios.create({
  baseURL: import.meta.env.VITE_APP_BASE_API,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json;charset=utf-8' }
})

service.interceptors.request.use(async config => {
  let mutationFingerprint = null
  try {
    if (config.headers?.isToken !== false && getToken()) {
      config.headers.Authorization = `Bearer ${getToken()}`
    }
    mutationFingerprint = checkDuplicateMutation(config)
    return wrapRequestAdapter(await encryptTransportRequest(config))
  } catch (error) {
    if (mutationFingerprint && error?.kind !== 'DUPLICATE_MUTATION') {
      recentMutations.delete(mutationFingerprint)
    }
    if (error?.__requestClassified) {
      error.suppressErrorMessage = Boolean(config.suppressErrorMessage)
      throw error
    }
    const classifiedError = createRequestError(error?.message || '请求发送前处理失败', {
      kind: 'REQUEST_SETUP',
      requestSent: false,
      cause: error
    })
    classifiedError.suppressErrorMessage = Boolean(config.suppressErrorMessage)
    throw classifiedError
  }
})

service.interceptors.response.use(
  async response => {
    try {
      response = await decryptTransportResponse(response)
    } catch (error) {
      throw createRequestError(error?.message || '响应解密失败', {
        kind: 'RESPONSE_PROCESSING',
        requestSent: true,
        status: response?.status,
        cause: error
      })
    }
    if (['blob', 'arraybuffer'].includes(response.config.responseType)) return response.data
    const payload = response.data || {}
    const code = Number(payload.code ?? 200)
    if (code === 401) {
      await handleUnauthorized()
      throw createRequestError(payload.msg || '登录状态已失效，请重新登录', {
        kind: 'BUSINESS',
        requestSent: true,
        status: code,
        data: payload.data
      })
    }
    if (code !== 200) {
      const message = payload.msg || '请求失败'
      if (shouldShowError(response.config)) ElMessage.error(message)
      throw createRequestError(message, {
        kind: code >= 500 ? 'HTTP_SERVER' : 'BUSINESS',
        requestSent: true,
        status: code,
        data: payload.data
      })
    }
    return payload
  },
  async error => {
    if (error?.__requestClassified) {
      if (shouldShowError(error.config, error)) ElMessage.error(error.message)
      throw error
    }
    error = await decryptTransportErrorResponse(error)
    if (shouldRetryTransportWithFreshKey(error) && error.config && !error.config.__transportRetried) {
      invalidateTransportKeyMeta()
      error.config.__transportRetried = true
      error.config.headers = error.config.headers || {}
      error.config.headers.repeatSubmit = false
      delete error.config.__requestSent
      resetTransportRequestConfig(error.config)
      return service.request(error.config)
    }
    if (error.response?.status === 401 || Number(error.response?.data?.code) === 401) {
      await handleUnauthorized()
    }
    const message =
      error.response?.data?.msg ||
      (error.code === 'ECONNABORTED' ? '系统接口请求超时' : error.message) ||
      '后端接口连接异常'
    if (shouldShowError(error.config, error)) ElMessage.error(message)
    const status = Number(error.response?.status || error.response?.data?.code || 0)
    const requestSent = Boolean(error.response || error.config?.__requestSent)
    const kind = !requestSent
      ? 'REQUEST_SETUP'
      : ['ECONNABORTED', 'ETIMEDOUT'].includes(error.code)
        ? 'TIMEOUT'
        : status >= 500
          ? 'HTTP_SERVER'
          : status > 0
            ? 'HTTP_CLIENT'
            : 'NETWORK'
    throw createRequestError(message, {
      kind,
      requestSent,
      status,
      data: error.response?.data?.data,
      cause: error
    })
  }
)

export async function downloadFile(url, params, filename) {
  const data = await service.request({
    url,
    method: 'post',
    data: params,
    responseType: 'blob',
    headers: { encryptResponse: false }
  })
  const objectUrl = URL.createObjectURL(data instanceof Blob ? data : new Blob([data]))
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = filename
  link.click()
  URL.revokeObjectURL(objectUrl)
}

export default service
