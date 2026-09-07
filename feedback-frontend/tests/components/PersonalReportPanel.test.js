import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { expect, it } from 'vitest'
import PersonalReportPanel from '@/components/feedback/reports/PersonalReportPanel.vue'

it('表格区分零分、缺失和不适用，显示实际权重和漏答', async () => {
  const wrapper = mount(PersonalReportPanel, {
    global: { plugins: [ElementPlus] },
    props: { report: {
      targetName: '测试员工', targetDeptName: '研发', score: '0.00', selfScore: null, otherScore: '0.00',
      hasMissingData: true, onlySelfEvaluation: false, expectedCount: 2, submittedCount: 1, completionRate: '50.00',
      indicators: [{ indicatorId: 1, indicatorName: '协作', weight: '100.00', score: '0.00', selfScore: null, otherScore: '0.00', relations: [
        { relationId: 1, relationName: '上级', status: 'COMPLETE', expectedCount: 1, submittedCount: 1, score: '0.00', originalWeight: '50.00', effectiveWeight: '100.00', missingAnswerCount: 0 },
        { relationId: 2, relationName: '同级', status: 'MISSING', expectedCount: 1, submittedCount: 0, score: null, originalWeight: '50.00', effectiveWeight: '0.00', missingAnswerCount: 0 },
        { relationId: 3, relationName: '下级', status: 'NOT_APPLICABLE', expectedCount: 0, submittedCount: 0, score: null, originalWeight: '0.00', effectiveWeight: '0.00', missingAnswerCount: 0 }
      ] }], questions: [{ questionId: 1, title: '建议', questionType: 'TEXT', isScored: false, relationName: '同级', submittedCount: 1, answeredCount: 0, missingAnswerCount: 1 }]
    } }
  })
  await flushPromises()
  expect(wrapper.text()).toContain('0.00')
  expect(wrapper.text()).toContain('最终得分来自他评加权，自评仅供对照')
  expect(wrapper.text()).toContain('他评加权分')
  expect(wrapper.text()).toContain('自评参考分')
  expect(wrapper.text()).toContain('数据不足')
  expect(wrapper.text()).toContain('缺失关系')
  expect(wrapper.text()).toContain('不适用')
  expect(wrapper.text()).toContain('实际权重')
  expect(wrapper.text()).toContain('不计分')
  expect(wrapper.text()).not.toContain('导出')
  wrapper.unmount()
})
