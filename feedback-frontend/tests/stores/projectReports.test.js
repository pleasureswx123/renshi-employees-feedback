import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, it, vi } from 'vitest'
import * as api from '@/api/feedback/reports'
import { useProjectReportsStore } from '@/stores/projectReports'
import { useAuthStore } from '@/stores/auth'
import { usePermissionStore } from '@/stores/permission'

vi.mock('@/api/feedback/reports', () => ({
  getTeamReport: vi.fn(), generateReports: vi.fn(), getPersonalReport: vi.fn(),
  getSubmittedAnswer: vi.fn(), listReportProjects: vi.fn(), listSubmittedAnswers: vi.fn()
}))
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r }); return { promise, resolve } }
beforeEach(() => { setActivePinia(createPinia()); vi.resetAllMocks() })

it('切换项目立即清理原文并丢弃旧响应', async () => {
  const store = useProjectReportsStore()
  store.selectProject(1)
  const pending = deferred()
  api.getSubmittedAnswer.mockReturnValue(pending.promise)
  const old = store.loadAnswer(9)
  store.selectProject(2)
  pending.resolve({ data: { answers: ['旧答案'] } })
  expect(await old).toBeNull()
  expect(store.answer).toBeNull()
  expect(store.projectId).toBe(2)
})

it('关闭抽屉后迟到的个人报告不恢复', async () => {
  const store = useProjectReportsStore()
  store.selectProject(1)
  const pending = deferred()
  api.getPersonalReport.mockReturnValue(pending.promise)
  const old = store.loadPerson(9)
  store.clear('person')
  pending.resolve({ data: { score: '80.00' } })
  await old
  expect(store.person).toBeNull()
})

it('禁止重复生成，成功后重新查询正式报告', async () => {
  const store = useProjectReportsStore()
  store.selectProject(1)
  const pending = deferred()
  api.generateReports.mockReturnValue(pending.promise)
  api.getTeamReport.mockResolvedValue({ data: { ready: true } })
  const generating = store.generate()
  expect(await store.generate()).toBeNull()
  pending.resolve({ data: { calculatedCount: 2 } })
  await generating
  expect(api.generateReports).toHaveBeenCalledTimes(1)
  expect(store.team.ready).toBe(true)
})

it.each([403, 404])('权限或范围丢失 %s 时清空所有敏感展示', async status => {
  const store = useProjectReportsStore()
  store.selectProject(1)
  store.person = { score: '80.00' }
  store.answer = { answers: ['敏感答案'] }
  api.getTeamReport.mockRejectedValue({ status, message: '不可访问' })
  await store.loadTeam(1)
  expect(store.team).toBeNull()
  expect(store.person).toBeNull()
  expect(store.answer).toBeNull()
  expect(store.errors.team).toBe('不可访问')
})

it('退出清理原文与报告，迟到的生成响应不重载', async () => {
  const store = useProjectReportsStore()
  store.selectProject(1)
  const pending = deferred()
  api.generateReports.mockReturnValue(pending.promise)
  const generating = store.generate()
  useAuthStore().clearSession()
  pending.resolve({ data: { calculatedCount: 1 } })
  await generating
  expect(store.projectId).toBeNull()
  expect(api.getTeamReport).not.toHaveBeenCalled()
})

it.each([['feedback:report:view', '/hr/reports'], ['feedback:answer:view', '/hr/answers']])('独立权限 %s 获得可用入口', (permission, path) => {
  useAuthStore().permissions = [permission]
  expect(usePermissionStore().defaultPath()).toBe(path)
})
