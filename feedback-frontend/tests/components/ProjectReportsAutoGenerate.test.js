import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, RouterView } from 'vue-router'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus, { ElMessage } from 'element-plus'
import { beforeEach, afterEach, it, expect, vi } from 'vitest'
import ProjectReportsView from '@/views/hr/ProjectReportsView.vue'
import { useAuthStore } from '@/stores/auth'
import { useProjectReportsStore } from '@/stores/projectReports'

const api = vi.hoisted(() => ({ getTeamReport: vi.fn(), generateReports: vi.fn(), getPersonalReport: vi.fn(), getSubmittedAnswer: vi.fn(), listReportProjects: vi.fn(), listSubmittedAnswers: vi.fn() }))
vi.mock('@/api/feedback/reports', () => api)
let wrapper, router
const report = ready => ({ ready, projectName: '测试项目', dataScopeComplete: true, rows: [], total: 0, targetCount: 1, submittedCount: 1, expectedCount: 1, completionRate: '100.00' })
async function open() {
  const pinia = createPinia()
  setActivePinia(pinia)
  useAuthStore().permissions = ['feedback:report:view']
  router = createRouter({ history: createMemoryHistory(), routes: [
    { path: '/projects/:projectId/reports', component: ProjectReportsView },
    { path: '/other', component: { template: '<div>其他页面</div>' } }
  ] })
  await router.push('/projects/1/reports')
  wrapper = mount(RouterView, { global: { plugins: [pinia, router, ElementPlus] } })
  await flushPromises()
}
beforeEach(() => { Object.values(api).forEach(fn => fn.mockReset()) })
afterEach(() => { wrapper?.unmount(); ElMessage.closeAll() })

it('首次进入自动生成并展示，已有报告刷新不重复计算', async () => {
  api.getTeamReport.mockResolvedValueOnce({ data: report(false) }).mockResolvedValue({ data: report(true) })
  api.generateReports.mockResolvedValue({ data: { calculatedCount: 1 } })
  await open()
  expect(api.generateReports).toHaveBeenCalledExactlyOnceWith(1)
  expect(wrapper.text()).toContain('团队排名与明细')
  await wrapper.findAll('button').find(button => button.text() === '刷新').trigger('click')
  await flushPromises()
  expect(api.generateReports).toHaveBeenCalledTimes(1)
})

it('已有报告或读取失败不触发生成', async () => {
  api.getTeamReport.mockResolvedValue({ data: report(true) })
  await open()
  expect(api.generateReports).not.toHaveBeenCalled()
  api.getTeamReport.mockRejectedValue({ status: 403, message: '无报告权限' })
  await router.push('/projects/2/reports')
  await flushPromises()
  expect(api.generateReports).not.toHaveBeenCalled()
  expect(wrapper.text()).toContain('无报告权限')
})

it('生成失败停止自动重试，用户可以明确重试', async () => {
  api.getTeamReport.mockResolvedValue({ data: report(false) })
  api.generateReports.mockRejectedValueOnce(new Error('生成失败')).mockResolvedValue({ data: { calculatedCount: 1 } })
  await open()
  expect(wrapper.text()).toContain('生成失败')
  expect(api.generateReports).toHaveBeenCalledTimes(1)
  api.getTeamReport.mockResolvedValue({ data: report(true) })
  await wrapper.findAll('button').find(button => button.text() === '重试生成报告').trigger('click')
  await flushPromises()
  expect(api.generateReports).toHaveBeenCalledTimes(2)
  expect(wrapper.text()).toContain('团队排名与明细')
})

it('生成期间切换项目不阻塞新项目，旧响应不覆盖新页面', async () => {
  let finish
  api.getTeamReport.mockImplementation(async id => ({ data: report(id === 2) }))
  api.generateReports.mockReturnValue(new Promise(resolve => { finish = resolve }))
  await open()
  expect(wrapper.text()).toContain('正在生成报告')
  await router.push('/projects/2/reports')
  await flushPromises()
  expect(useProjectReportsStore().projectId).toBe(2)
  expect(wrapper.text()).toContain('团队排名与明细')
  finish({ data: { calculatedCount: 1 } })
  await flushPromises()
  expect(api.getTeamReport.mock.calls.map(call => call[0])).toEqual([1, 2])
})

it('离开页面后迟到的读取响应不会生成报告', async () => {
  let finish
  api.getTeamReport.mockReturnValue(new Promise(resolve => { finish = resolve }))
  await open()
  await router.push('/other')
  await flushPromises()
  finish({ data: report(false) })
  await flushPromises()
  expect(api.generateReports).not.toHaveBeenCalled()
})


it('主表突出最终得分并区分零分、缺失和仅自评，详情保留入口', async () => {
  const rows = [
    { targetUserId: 1, targetName: '零分员工', score: '0.00', selfScore: '80.00', onlySelfEvaluation: false },
    { targetUserId: 2, targetName: '仅自评员工', score: '90.00', selfScore: '90.00', onlySelfEvaluation: true },
    { targetUserId: 3, targetName: '缺少他评员工', score: null, selfScore: '70.00', onlySelfEvaluation: false },
    { targetUserId: 4, targetName: '缺少自评员工', score: null, selfScore: null, onlySelfEvaluation: true }
  ].map(row => ({ ...row, submittedCount: 1, expectedCount: 2, completionRate: '50.00', hasMissingData: true }))
  api.getTeamReport.mockResolvedValue({ data: { ...report(true), rows, total: 4 } })
  await open()
  const headers = wrapper.findAll('th').map(cell => cell.text())
  expect(headers).toContain('最终得分')
  expect(headers).toContain('自评参考分')
  expect(headers).not.toContain('他评分')
  expect(headers).not.toContain('指标分')
  const cells = wrapper.findAll('.el-table__body tbody tr')
  expect(cells[0].text()).toContain('0.00')
  expect(cells[0].text()).toContain('仅供对照，不计入最终得分')
  expect(cells[1].text()).toContain('仅自评 · 以自评计分')
  expect(cells[2].text()).toContain('他评数据不足')
  expect(cells[3].text()).toContain('自评数据不足')
  api.getPersonalReport.mockResolvedValue({ data: { ...rows[1], indicators: [], questions: [] } })
  await cells[1].findAll('button').find(button => button.text() === '查看得分详情').trigger('click')
  await flushPromises()
  expect(api.getPersonalReport).toHaveBeenCalledWith(1, 2)
  expect(wrapper.text()).toContain('最终得分按自评及指标权重计算')
})
