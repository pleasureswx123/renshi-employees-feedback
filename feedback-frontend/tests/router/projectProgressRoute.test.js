import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import router from '@/router'
import { useAuthStore } from '@/stores/auth'

describe('P7进度路由与权限守卫', () => {
  beforeEach(async () => {
    setActivePinia(createPinia())
    const auth = useAuthStore()
    auth.token = 'route-token'
    auth.initialized = true
    auth.user = { userName: 'tester' }
    await router.replace('/login')
  })

  it('进度路由仅声明feedback:progress:view且子路由高亮项目菜单', () => {
    const record = router.getRoutes().find(item => item.name === 'hr-project-progress')
    expect(record.path).toBe('/hr/projects/:projectId/progress')
    expect(record.meta.permissions).toEqual(['feedback:progress:view'])
    expect(record.meta.activeMenu).toBe('/hr/projects')
  })

  it('安全进度入口同样只要求feedback:progress:view', () => {
    const record = router.getRoutes().find(item => item.name === 'hr-progress-entry')
    expect(record.path).toBe('/hr/progress')
    expect(record.meta.permissions).toEqual(['feedback:progress:view'])
  })

  it('普通员工和只有完成权限的HR都不能进入进度页', async () => {
    const auth = useAuthStore()
    auth.permissions = ['feedback:task:view']
    await router.push('/hr/projects/12/progress')
    expect(router.currentRoute.value.path).toBe('/403')

    auth.permissions = ['feedback:project:complete']
    await router.push('/hr/projects/12/progress')
    expect(router.currentRoute.value.path).toBe('/403')
  })

  it('只有进度权限即可进入页面但不因此获得完成权限', async () => {
    const auth = useAuthStore()
    auth.permissions = ['feedback:progress:view']
    await router.push('/hr/projects/12/progress')
    expect(router.currentRoute.value.path).toBe('/hr/projects/12/progress')
    expect(auth.permissions).not.toContain('feedback:project:complete')
  })
})
