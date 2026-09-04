export function workspaceMenuItems(workspace, hasPermission) {
  if (workspace === 'hr') {
    return [
      hasPermission('feedback:project:list')
        ? { path: '/hr/projects', label: '评价项目', icon: 'project' }
        : hasPermission('feedback:progress:view')
          ? { path: '/hr/progress', label: '回收进度', icon: 'report' }
          : null,
      hasPermission('feedback:report:view') ? { path: '/hr/reports', label: '评价报告', icon: 'report' } : null,
      hasPermission('feedback:answer:view') ? { path: '/hr/answers', label: '原始答案', icon: 'answers' } : null
    ].filter(Boolean)
  }
  return [
    hasPermission('feedback:task:view') ? { path: '/employee/todos', label: '我的待办', icon: 'todos' } : null,
    hasPermission('feedback:history:view') ? { path: '/employee/reviews', label: '我评价的', icon: 'history' } : null
  ].filter(Boolean)
}

export function activeWorkspaceMenu(route, items) {
  const path = route.meta.activeMenu || route.path
  if (path === '/hr/projects' && !items.some(item => item.path === path)) {
    return items.find(item => item.path === '/hr/progress') || null
  }
  return items.find(item => item.path === path) || null
}
