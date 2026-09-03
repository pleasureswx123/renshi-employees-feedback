import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, it } from 'vitest'
import router from '@/router'
import { useAuthStore } from '@/stores/auth'

beforeEach(async () => {
  setActivePinia(createPinia())
  const auth = useAuthStore()
  auth.token = 'route-test'
  auth.initialized = true
  await router.replace('/403')
})

it('只有报告权限也能进入报告列表，不能进入原始答案', async () => {
  useAuthStore().permissions = ['feedback:report:view']
  await router.push('/hr/reports')
  expect(router.currentRoute.value.path).toBe('/hr/reports')
  await router.push('/hr/projects/1/reports')
  expect(router.currentRoute.value.path).toBe('/hr/projects/1/reports')
  await router.push('/hr/projects/1/answers')
  expect(router.currentRoute.value.path).toBe('/403')
})

it('答案权限独立，普通员工不能进入报告', async () => {
  useAuthStore().permissions = ['feedback:answer:view']
  await router.push('/hr/projects/1/answers')
  expect(router.currentRoute.value.path).toBe('/hr/projects/1/answers')
  useAuthStore().permissions = ['feedback:task:view']
  await router.push('/hr/projects/1/reports')
  expect(router.currentRoute.value.path).toBe('/403')
})
