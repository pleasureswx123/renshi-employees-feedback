import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus, { ElSelect } from 'element-plus'
import { expect, it } from 'vitest'
import IndicatorComparison from '@/components/feedback/reports/IndicatorComparison.vue'

it('按指标ID对齐不同人员，默认展开多层表头并支持筛选单个指标', async () => {
  const indicators = [
    { indicatorId: 1, indicatorName: '团队合作', weight: '60.00', score: '0.00', relations: [
      { relationId: 8, relationName: '上级', relationType: 'SUPERIOR', score: '0.00', status: 'COMPLETE', submittedCount: 1, expectedCount: 1, originalWeight: '60.00', effectiveWeight: '100.00' },
      { relationId: 9, relationName: '同级', score: null, status: 'MISSING', submittedCount: 0, expectedCount: 1, originalWeight: '0.00', effectiveWeight: '0.00' }
    ] },
    { indicatorId: 2, indicatorName: '领导力', weight: '40.00', score: '80.00', relations: [] }
  ]
  const rows = [{ targetUserId: 1, targetName: '甲', score: '32.00', indicators, relations: indicators[0].relations, relationScores: { 8: '0.00', 9: null } }, { targetUserId: 2, targetName: '乙', score: null, onlySelfEvaluation: true, indicators: [...indicators].reverse() }]
  const wrapper = mount(IndicatorComparison, { props: { rows }, global: { plugins: [ElementPlus] } })
  await flushPromises()
  expect(wrapper.text()).toContain('团队合作')
  expect(wrapper.text()).toContain('领导力')
  expect(wrapper.text()).toContain('仅自评 · 以自评计分')
  expect(wrapper.findAll('tbody tr')[1].text()).toMatch(/0.00.*80.00/)
  expect(wrapper.findAll('thead tr')).toHaveLength(2)
  const headers = wrapper.findAll('thead tr')
  expect(headers[0].findAll('th').slice(0, 6).map(cell => cell.text())).toEqual(['部门', '被评价人', '总得分', '上级', '同级', '自己'])
  expect(headers[0].text()).toContain('权重 60.00%')
  expect(headers[1].findAll('th').slice(0, 4).map(cell => cell.text())).toEqual(['上级权重 60.00%', '同级权重 0.00%', '自己', '综合平均'])
  expect(headers[0].findAll('.relation-weight')).toHaveLength(0)
  expect(headers[1].findAll('.relation-weight').map(item => item.text())).toEqual(['权重 60.00%', '权重 0.00%'])
  expect(wrapper.findAll('tbody tr')[0].findAll('td').slice(3, 6).map(cell => cell.text())).toEqual(['0.00', '数据不足', '—'])
  await wrapper.findAll('tbody tr')[0].findAll('td')[3].get('button').trigger('click')
  expect(wrapper.emitted('source')[0][0]).toEqual({ row: rows[0], key: 'r-8-average' })
  wrapper.findComponent(ElSelect).vm.$emit('update:modelValue', 1)
  await flushPromises()
  expect(wrapper.text()).toContain('未提交')
  expect(wrapper.findAll('thead tr')).toHaveLength(2)
  expect(wrapper.findAll('thead tr')[1].text()).toContain('上级')
  expect(wrapper.findAll('thead tr')[0].text()).not.toContain('领导力')
  expect(wrapper.text()).toContain('数据不足')
  await wrapper.findAll('tbody button').find(button => button.text() === '查看得分详情').trigger('click')
  expect(wrapper.emitted('detail')[0][0].targetUserId).toBe(1)
  await wrapper.setProps({ rows: [] })
  expect(wrapper.findComponent(ElSelect).props('modelValue')).toBe('all')
  expect(wrapper.text()).not.toContain('实际权重 100.00%')
  wrapper.unmount()
})
