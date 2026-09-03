import { beforeEach, expect, it, vi } from 'vitest'
import request from '@/utils/request'
import { generateReports, getPersonalReport, getSubmittedAnswer, getTeamReport, listReportProjects, listSubmittedAnswers } from '@/api/feedback/reports'

vi.mock('@/utils/request', () => ({ default: vi.fn().mockResolvedValue({}) }))
beforeEach(() => vi.clearAllMocks())
it('报告与原始答案使用独立接口和现有请求链路', async () => {
  await listReportProjects({ pageNum: 2 })
  await getTeamReport(12, { keyword: '小李' })
  await generateReports(12)
  await getPersonalReport(12, 8)
  await listSubmittedAnswers(12, { targetUserId: 8 })
  await getSubmittedAnswer(12, 9)
  expect(request.mock.calls.map(([config]) => config)).toEqual([
    { url: '/feedback/reports/projects', method: 'get', params: { pageNum: 2 } },
    { url: '/feedback/projects/12/reports', method: 'get', params: { keyword: '小李' } },
    { url: '/feedback/projects/12/reports/calculate', method: 'post' },
    { url: '/feedback/projects/12/reports/8', method: 'get' },
    { url: '/feedback/projects/12/answers', method: 'get', params: { targetUserId: 8 } },
    { url: '/feedback/projects/12/answers/9', method: 'get' }
  ])
})
