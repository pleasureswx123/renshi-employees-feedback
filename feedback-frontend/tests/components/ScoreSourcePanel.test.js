import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ElementPlus from 'element-plus'
import { expect, it, vi, beforeEach } from 'vitest'
import ScoreSourcePanel from '@/components/feedback/reports/ScoreSourcePanel.vue'
import { useAuthStore } from '@/stores/auth'
import { useProjectReportsStore } from '@/stores/projectReports'
const api = vi.hoisted(() => ({ getScoreSource: vi.fn(), getScoreSourceSheets: vi.fn() }))
vi.mock('@/api/feedback/reports', () => api)
const source = { targetName: '甲', rows: [
  { key: 'total', label: '最终得分', level: 'total', formula: '83 × 100%', result: '83.00' },
  { key: 'i-1', parentKey: 'total', level: 'indicator', label: '团队合作', formula: '90 × 50% + 80 × 30% + 70 × 20%', result: '83.00' },
  { key: 'i-1-r-1', parentKey: 'i-1', level: 'relation', label: '团队合作 · 上级', formula: '90 ÷ 1', result: '90.00', indicatorId: 1, relationId: 1 }
] }
beforeEach(() => { vi.resetAllMocks() })
function open(permissions = ['feedback:report:view']) {
  const pinia = createPinia(); setActivePinia(pinia)
  useAuthStore().permissions = permissions
  useProjectReportsStore().selectProject(1)
  return mount(ScoreSourcePanel, { props: { target: { row: { targetName: '甲', targetUserId: 2 }, key: 'i-1' } }, global: { plugins: [pinia, ElementPlus] } })
}
it('定位指标公式，报告权限不预取答卷明细', async () => {
  api.getScoreSource.mockResolvedValue({ data: source })
  const wrapper = open(); await flushPromises()
  expect(wrapper.text()).toContain('90 × 50%')
  expect(wrapper.text()).not.toContain('83 × 100%')
  expect(wrapper.text()).not.toContain('查看答卷公式')
  expect(api.getScoreSourceSheets).not.toHaveBeenCalled()
  wrapper.unmount()
  expect(useProjectReportsStore().source).toBeNull()
})
it('有权限时按需读取所选关系的答卷公式', async () => {
  api.getScoreSource.mockResolvedValue({ data: source })
  api.getScoreSourceSheets.mockResolvedValue({ data: { rows: [{ key: 's1', level: 'sheet', label: '上级答卷1', formula: '90 ÷ 100 × 100', result: '90.00' }] } })
  const wrapper = open(['feedback:report:view', 'feedback:answer:view']); await flushPromises()
  await wrapper.findAll('button').find(button => button.text() === '查看答卷公式').trigger('click')
  await flushPromises()
  expect(api.getScoreSourceSheets).toHaveBeenCalledWith(1, 2, { indicatorId: 1, relationId: 1 })
  expect(wrapper.text()).toContain('90 ÷ 100 × 100')
  wrapper.unmount()
})
it('切换人员后丢弃旧公式响应', async () => {
  let finish
  api.getScoreSource.mockReturnValueOnce(new Promise(resolve => { finish = resolve })).mockResolvedValue({ data: { ...source, rows: [] } })
  const wrapper = open()
  await wrapper.setProps({ target: { row: { targetName: '乙', targetUserId: 3 }, key: 'total' } })
  await flushPromises()
  finish({ data: source }); await flushPromises()
  expect(wrapper.text()).not.toContain('90 × 50%')
  expect(wrapper.text()).toContain('乙 · 得分来源')
  wrapper.unmount()
})

it('直接点击关系分自动加载逐题依据与合计过程', async () => {
  api.getScoreSource.mockResolvedValue({ data: source })
  api.getScoreSourceSheets.mockResolvedValue({ data: { rows: [
    { key: 'r1', level: 'relation', label: '上级', formula: '(53.21) ÷ 1', result: '53.21' },
    { key: 's1', parentKey: 'r1', level: 'sheet', label: '上级答卷1', formula: '58 ÷ 109 × 100', earnedFormula: '8 + 50 = 58', maximumFormula: '9 + 100 = 109', result: '53.21' },
    { key: 'q1', parentKey: 's1', level: 'question', label: '测试题', rawScore: '8', maxScore: '9', note: '原始题分' }
  ] } })
  const wrapper = open(['feedback:report:view', 'feedback:answer:view'])
  await wrapper.setProps({ target: { row: { targetName: '甲', targetUserId: 2 }, key: 'i-1-r-1' } })
  await flushPromises()
  expect(api.getScoreSourceSheets).toHaveBeenCalledTimes(1)
  expect(wrapper.text()).toContain('8 + 50 = 58')
  expect(wrapper.text()).toContain('测试题')
  expect(wrapper.text()).toContain('对已提交答卷取平均')
  wrapper.unmount()
})
