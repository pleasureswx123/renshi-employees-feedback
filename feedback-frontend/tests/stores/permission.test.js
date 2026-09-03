import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { useAuthStore } from '@/stores/auth'
import { usePermissionStore } from '@/stores/permission'

describe('permission store', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('按权限并集开放HR和员工工作台', () => {
    const authStore = useAuthStore()
    authStore.permissions = ['feedback:project:list', 'feedback:task:view']
    const permissionStore = usePermissionStore()

    expect(permissionStore.canAccessWorkspace('hr')).toBe(true)
    expect(permissionStore.canAccessWorkspace('employee')).toBe(true)
    expect(permissionStore.availableWorkspaces().map(item => item.key)).toEqual(['hr', 'employee'])
  })

  it('员工权限不能打开HR工作台', () => {
    const authStore = useAuthStore()
    authStore.permissions = ['feedback:task:view', 'feedback:task:submit']
    const permissionStore = usePermissionStore()

    expect(permissionStore.canAccessWorkspace('hr')).toBe(false)
    expect(permissionStore.defaultPath()).toBe('/employee/todos')
  })

  it('系统管理员通配权限可以进入两个工作台', () => {
    const authStore = useAuthStore()
    authStore.permissions = ['*:*:*']
    const permissionStore = usePermissionStore()

    expect(permissionStore.availableWorkspaces()).toHaveLength(2)
  })

  it('progress-only用户默认进入安全回收进度入口而不是项目列表', () => {
    const authStore = useAuthStore()
    authStore.permissions = ['feedback:progress:view']
    const permissionStore = usePermissionStore()

    expect(permissionStore.availableWorkspaces()).toEqual([
      { key: 'hr', label: 'HR 工作台', path: '/hr/progress' }
    ])
    expect(permissionStore.defaultPath()).toBe('/hr/progress')
  })

  it('complete-only用户没有进度读取能力时不获得HR工作台入口', () => {
    const authStore = useAuthStore()
    authStore.permissions = ['feedback:project:complete']
    const permissionStore = usePermissionStore()

    expect(permissionStore.canAccessWorkspace('hr')).toBe(true)
    expect(permissionStore.availableWorkspaces()).toEqual([])
    expect(permissionStore.defaultPath()).toBe('/403')
  })
})
