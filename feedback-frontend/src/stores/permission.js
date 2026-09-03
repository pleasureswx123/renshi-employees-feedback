import { defineStore } from 'pinia'

import { useAuthStore } from './auth'

export const HR_ENTRY_PERMISSIONS = Object.freeze([
  'feedback:project:list',
  'feedback:project:add',
  'feedback:project:edit',
  'feedback:project:publish',
  'feedback:project:complete',
  'feedback:questionnaire:edit',
  'feedback:participant:manage',
  'feedback:progress:view',
  'feedback:report:view',
  'feedback:answer:view'
])

export const EMPLOYEE_ENTRY_PERMISSIONS = Object.freeze([
  'feedback:task:view',
  'feedback:task:answer',
  'feedback:task:submit',
  'feedback:history:view'
])

export const usePermissionStore = defineStore('permission', () => {
  const authStore = useAuthStore()

  function hasPermission(permission) {
    return authStore.permissions.includes('*:*:*') || authStore.permissions.includes(permission)
  }

  function hasAnyPermission(permissions) {
    return permissions.some(hasPermission)
  }

  function canAccessWorkspace(workspace) {
    if (workspace === 'hr') return hasAnyPermission(HR_ENTRY_PERMISSIONS)
    if (workspace === 'employee') return hasAnyPermission(EMPLOYEE_ENTRY_PERMISSIONS)
    return false
  }

  function hrWorkspacePath() {
    if (hasPermission('feedback:project:list')) return '/hr/projects'
    if (hasPermission('feedback:progress:view')) return '/hr/progress'
    if (hasPermission('feedback:report:view')) return '/hr/reports'
    if (hasPermission('feedback:answer:view')) return '/hr/answers'
    return null
  }

  function availableWorkspaces() {
    const hrPath = hrWorkspacePath()
    return [
      hrPath ? { key: 'hr', label: 'HR 工作台', path: hrPath } : null,
      canAccessWorkspace('employee')
        ? { key: 'employee', label: '员工工作台', path: hasPermission('feedback:task:view') ? '/employee/todos' : hasPermission('feedback:history:view') ? '/employee/reviews' : '/403' }
        : null
    ].filter(Boolean)
  }

  function defaultPath() {
    return availableWorkspaces()[0]?.path || '/403'
  }

  return {
    hasPermission,
    hasAnyPermission,
    canAccessWorkspace,
    hrWorkspacePath,
    availableWorkspaces,
    defaultPath
  }
})
