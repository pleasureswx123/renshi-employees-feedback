function getStorage() {
  if (typeof window === 'undefined') {
    return null
  }
  return window.sessionStorage
}

export function getSessionJson(key) {
  try {
    const value = getStorage()?.getItem(key)
    return value ? JSON.parse(value) : null
  } catch {
    return null
  }
}

export function setSessionJson(key, value) {
  try {
    getStorage()?.setItem(key, JSON.stringify(value))
  } catch {
    // 会话缓存不可用时继续使用进程内状态，不阻断业务请求。
  }
}

export function removeSessionItem(key) {
  try {
    getStorage()?.removeItem(key)
  } catch {
    // 缓存清理失败不影响下一次从后端刷新配置。
  }
}
