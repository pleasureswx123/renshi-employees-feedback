export const overviewPermissions = Object.freeze({
  users: 'system:user:list',
  departments: 'system:dept:list',
  roles: 'system:role:list'
})

export function emptyOverview() {
  return Object.fromEntries(Object.keys(overviewPermissions).map(key => [key, { status: 'idle', value: null }]))
}

// 复用列表接口的总数和部门结果，不下载完整用户或角色名册。
export async function loadManagementOverview(canRead, loaders) {
  const entries = await Promise.all(Object.entries(overviewPermissions).map(async ([key, permission]) => {
    if (!canRead(permission)) return [key, { status: 'forbidden', value: null }]
    try {
      const response = await loaders[key](key === 'departments' ? {} : { pageNum: 1, pageSize: 1 })
      const value = key === 'departments'
        ? (Array.isArray(response?.data) ? response.data.length : null)
        : response?.total
      if (!Number.isSafeInteger(value) || value < 0) throw new Error('概览统计响应不完整')
      return [key, { status: 'success', value }]
    } catch {
      // 请求层负责错误提示；首页保留独立失败状态，不能把失败显示成零。
      return [key, { status: 'error', value: null }]
    }
  }))
  return Object.fromEntries(entries)
}

export function resolveFeedbackEntry(value) {
  if (typeof value !== 'string' || !value.trim()) return ''
  try {
    const url = new URL(value.trim())
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) return ''
    return url.href
  } catch {
    return ''
  }
}
