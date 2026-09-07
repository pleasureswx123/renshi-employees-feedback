import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { expect, it, vi } from 'vitest'
import ReportScoreChart from '@/components/feedback/reports/ReportScoreChart.vue'
const charts = vi.hoisted(() => [])
vi.mock('echarts/core', () => ({ init: () => { const chart = { setOption: vi.fn(), resize: vi.fn(), dispose: vi.fn(), on: vi.fn() }; charts.push(chart); return chart }, use: vi.fn() }))
it('同时显示最终分和全部指标，保持缺失语义、来源定位并释放移除的图表', async () => {
  const rows = [
    { targetUserId: 1, targetName: '甲', score: '0.00', indicators: [{ indicatorId: 7, indicatorName: '团队合作', weight: '60', score: '25.00' }, { indicatorId: 8, indicatorName: '领导力', weight: '40', score: '30.00' }] },
    { targetUserId: 2, targetName: '乙', score: null, indicators: [{ indicatorId: 7, indicatorName: '团队合作', weight: '60', score: null }, { indicatorId: 8, indicatorName: '领导力', weight: '40', score: '50.00' }] }
  ]
  const wrapper = mount(ReportScoreChart, { props: { rows }, global: { plugins: [ElementPlus] } })
  await flushPromises()
  expect(charts).toHaveLength(3)
  expect(wrapper.findAll('h3').map(item => item.text())).toEqual(['最终得分', '团队合作', '领导力'])
  expect(wrapper.text()).not.toContain('比较内容')
  expect(charts.map(chart => chart.setOption.mock.calls.at(-1)[0].series[0].data)).toEqual([[0, null], [25, null], [30, 50]])
  expect(charts.every(chart => chart.setOption.mock.calls.at(-1)[0].xAxis.max === 100)).toBe(true)
  charts[1].on.mock.calls[0][1]({ componentType: 'series', dataIndex: 0 })
  expect(wrapper.emitted('source')[0][0].key).toBe('i-7')
  await wrapper.setProps({ rows: [] }); await flushPromises()
  expect(charts.every(chart => chart.dispose.mock.calls.length === 1)).toBe(true)
  wrapper.unmount()
})
