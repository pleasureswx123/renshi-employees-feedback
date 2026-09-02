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
  if (!['post', 'put', 'patch'].includes(method) || config.headers?.repeatSubmit === false) return
  const fingerprint = `${method}:${config.url}:${JSON.stringify(config.data ?? null)}`
  const currentTime = Date.now()
  const interval = Number(config.headers?.repeatInterval || 1000)
  if (currentTime - Number(recentMutations.get(fingerprint) || 0) < interval) {
    throw new Error('请求正在处理中，请勿重复提交')
  }
  recentMutations.set(fingerprint, currentTime)
}

const service = axios.create({
  baseURL: import.meta.env.VITE_APP_BASE_API,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json;charset=utf-8' }
})

service.interceptors.request.use(async config => {
  if (config.headers?.isToken !== false && getToken()) {
    config.headers.Authorization = `Bearer ${getToken()}`
  }
  checkDuplicateMutation(config)
  return encryptTransportRequest(config)
})

service.interceptors.response.use(
  async response => {
    response = await decryptTransportResponse(response)
    if (['blob', 'arraybuffer'].includes(response.config.responseType)) return response.data
    const payload = response.data || {}
    const code = Number(payload.code ?? 200)
    if (code === 401) {
      await handleUnauthorized()
      throw new Error(payload.msg || '登录状态已失效，请重新登录')
    }
    if (code !== 200) {
      const message = payload.msg || '请求失败'
      ElMessage.error(message)
      const businessError = new Error(message)
      businessError.status = code
      businessError.data = payload.data
      throw businessError
    }
    return payload
  },
  async error => {
    error = await decryptTransportErrorResponse(error)
    if (shouldRetryTransportWithFreshKey(error) && error.config && !error.config.__transportRetried) {
      invalidateTransportKeyMeta()
      error.config.__transportRetried = true
      error.config.headers = error.config.headers || {}
      error.config.headers.repeatSubmit = false
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
    ElMessage.error(message)
    const requestError = new Error(message)
    requestError.status = Number(error.response?.status || error.response?.data?.code || 0)
    requestError.data = error.response?.data?.data
    throw requestError
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
