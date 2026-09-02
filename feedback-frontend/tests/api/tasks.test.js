import { expect, it, vi } from 'vitest'

const request = vi.hoisted(() => vi.fn().mockResolvedValue({ code: 200 }))
vi.mock('@/utils/request', () => ({ default: request }))
const api = await import('@/api/feedback/tasks')

it('员工端使用同一认证请求基础设施，草稿和提交为不同接口', async () => {
  await api.listMyProjects({ pageNum: 1 })
  await api.getMyProject(2)
  await api.getMyTask(3)
  await api.saveMyDraft(3, { lockVersion: 0, answers: [] })
  await api.submitMyAnswer(3, { submissionId: 'request-id' })
  await api.listMyHistory({ pageNum: 1 })
  await api.getMyHistory(3)
  expect(request.mock.calls.map(([config]) => [config.method, config.url])).toEqual([
    ['get', '/feedback/employee/projects'], ['get', '/feedback/employee/projects/2'],
    ['get', '/feedback/employee/tasks/3'], ['put', '/feedback/employee/tasks/3/draft'],
    ['post', '/feedback/employee/tasks/3/submit'], ['get', '/feedback/employee/history'],
    ['get', '/feedback/employee/history/3']
  ])
})
