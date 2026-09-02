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
  'feedback:report:view'
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

  function availableWorkspaces() {
    return [
      canAccessWorkspace('hr') ? { key: 'hr', label: 'HR 工作台', path: '/hr/projects' } : null,
      canAccessWorkspace('employee')
        ? { key: 'employee', label: '员工工作台', path: '/employee/todos' }
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
    availableWorkspaces,
    defaultPath
  }
})
