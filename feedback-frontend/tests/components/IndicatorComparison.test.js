import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus, { ElSelect } from 'element-plus'
import { expect, it } from 'vitest'
import IndicatorComparison from '@/components/feedback/reports/IndicatorComparison.vue'

it('按指标ID对齐不同人员，默认展开多层表头并支持筛选单个指标', async () => {
  const indicators = [
    { indicatorId: 1, indicatorName: '团队合作', weight: '60.00', score: '0.00', relations: [
      { relationId: 8, relationName: '上级', relationType: 'SUPERIOR', score: '0.00', status: 'COMPLETE', submittedCount: 1, expectedCount: 1, effectiveWeight: '100.00' },
      { relationId: 9, relationName: '同级', score: null, status: 'MISSING', submittedCount: 0, expectedCount: 1, effectiveWeight: '0.00' }
    ] },
    { indicatorId: 2, indicatorName: '领导力', weight: '40.00', score: '80.00', relations: [] }
  ]
  const rows = [{ targetUserId: 1, targetName: '甲', score: '32.00', indicators }, { targetUserId: 2, targetName: '乙', score: null, onlySelfEvaluation: true, indicators: [...indicators].reverse() }]
  const wrapper = mount(IndicatorComparison, { props: { rows }, global: { plugins: [ElementPlus] } })
  await flushPromises()
  expect(wrapper.text()).toContain('团队合作')
  expect(wrapper.text()).toContain('领导力')
  expect(wrapper.text()).toContain('仅自评 · 以自评计分')
  expect(wrapper.findAll('tbody tr')[1].text()).toMatch(/0.00.*80.00/)
  expect(wrapper.findAll('thead tr')).toHaveLength(2)
  expect(wrapper.findAll('thead tr')[1].text()).toContain('指标最终得分')
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
