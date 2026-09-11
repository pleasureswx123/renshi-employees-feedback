import ElementPlus from 'element-plus'
import { mount, flushPromises } from '@vue/test-utils'
import { expect, it } from 'vitest'
import PublicationConfigurationReview from '@/components/feedback/publication/PublicationConfigurationReview.vue'
import { frozenDetailsFixture } from '../fixtures/frozenPublication'

function config() {
  return { questionnaire: frozenDetailsFixture().questionnaire, targets: [{ userId: 10, nickName: '张三', deptName: '研发部' }], configuredParticipants: [{ userId: 11, nickName: '李四' }], relations: [{ relationCode: 'REL_SELF', relationName: '自己', isEnabled: true, weight: '0' }, { relationCode: 'REL_PEER', relationName: '同级', isEnabled: true, participatesInScore: true, weight: '100' }], evaluatorSelections: [{ targetUserId: 10, relationCode: 'REL_PEER', evaluatorUserIds: [11] }] }
}
it('完整预览五种题型、指标绑定和名单，试填不修改配置，返回入口定位五步', async () => {
  const value = config()
  const before = JSON.stringify(value)
  const wrapper = mount(PublicationConfigurationReview, { props: { config: value, canManage: true, canEditQuestionnaire: true }, global: { plugins: [ElementPlus] } })
  await flushPromises()
  expect(wrapper.findAll('.preview-question')).toHaveLength(5)
  expect(wrapper.text()).toContain('1. 协作评价')
  expect(wrapper.text()).toContain('70%')
  expect(wrapper.text()).toContain('李四')
  expect(wrapper.text()).toContain('张三（本人，自动添加）')
  await wrapper.get('input[type="radio"]').setValue(true)
  expect(JSON.stringify(value)).toBe(before)
  for (const label of ['返回修改问卷', '返回修改指标与权重', '返回修改被评价人', '返回修改评价关系', '返回修改评价人安排']) {
    await wrapper.findAll('button').find(button => button.text() === label).trigger('click')
  }
  expect(wrapper.emitted('edit')).toEqual([[0], [1], [2], [3], [4]])
  wrapper.unmount()
})
it('无修改权限仅预览，缺少问卷时明确提示', async () => {
  const value = config()
  value.questionnaire = null
  const wrapper = mount(PublicationConfigurationReview, { props: { config: value }, global: { plugins: [ElementPlus] } })
  await flushPromises()
  expect(wrapper.text()).toContain('问卷预览暂不可用')
  expect(wrapper.text()).not.toContain('返回修改')
  wrapper.unmount()
})
