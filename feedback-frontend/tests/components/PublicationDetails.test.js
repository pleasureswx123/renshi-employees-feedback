import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, expect, it } from 'vitest'
import PublicationDetails from '@/components/feedback/publication/PublicationDetails.vue'
import { useAuthStore } from '@/stores/auth'
import { frozenDetailsFixture } from '../fixtures/frozenPublication'

let wrapper
const people = [{ userId: 10, nickName: '发布时张三', deptName: '研发部' }, { userId: 11, nickName: '发布时李四', deptName: '原部门', available: false }]
function config(status = 'ACTIVE') {
  return { projectId: 101, projectStatus: status, editable: false, frozenDetails: frozenDetailsFixture(),
    targets: [{ ...people[0], onlySelfEvaluation: false }], configuredParticipants: people,
    relations: [{ relationCode: 'REL_SELF', relationName: '自评', isEnabled: true }, { relationCode: 'REL_PEER', relationName: '同级', isEnabled: true, participatesInScore: true, weight: '100' }],
    evaluatorSelections: [{ targetUserId: 10, relationCode: 'REL_SELF', evaluatorUserIds: [10] }, { targetUserId: 10, relationCode: 'REL_PEER', evaluatorUserIds: [11] }],
    preview: { targetCount: 1, evaluatorCount: 2, assignmentCount: 2, targetSummaries: [{ targetUserId: 10, selfCount: 1, nonSelfCount: 1, assignmentCount: 2 }] }
  }
}
async function open(value = config(), permissions = []) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useAuthStore().permissions = permissions
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: { template: '<div />' } }, { path: '/hr/projects/101/progress', component: { template: '<div />' } }] })
  await router.push('/')
  wrapper = mount(PublicationDetails, { props: { config: value }, global: { plugins: [pinia, ElementPlus, router] } })
  await flushPromises()
  return router
}
async function tab(name) { await wrapper.findAll('[role="tab"]').find(item => item.text() === name).trigger('click'); await flushPromises() }
afterEach(() => wrapper?.unmount())

it('已发布概要展示审计信息和实际任务口径，进度入口遵守权限', async () => {
  const router = await open(config(), ['feedback:progress:view'])
  expect(wrapper.text()).toContain('2026-09-04 15:49:14')
  expect(wrapper.text()).toContain('feedback-hr')
  expect(wrapper.text()).toContain('去重人数，包含自评人员')
  expect(wrapper.text()).not.toContain('可以发布')
  expect(wrapper.findAll('button').some(button => button.text() === '保存配置')).toBe(false)
  await wrapper.findAll('button').find(button => button.text() === '查看评价进度').trigger('click')
  await flushPromises()
  expect(router.currentRoute.value.path).toBe('/hr/projects/101/progress')
})

it('冻结问卷展示五题型、指标权重和跨页绑定定位，不出现答题或编辑控件', async () => {
  await open()
  await tab('问卷与指标')
  expect(wrapper.text()).toContain('选择后需说明原因')
  expect(wrapper.text()).toContain('70%')
  await wrapper.findAll('.indicator-questions button').find(button => button.text().includes('目标达成')).trigger('click')
  await flushPromises()
  expect(wrapper.get('.highlighted').text()).toContain('第 3 题 · 目标达成')
  expect(wrapper.get('.highlighted').text()).toContain('默认 50.5 分')
  expect(wrapper.get('.frozen-questionnaire').text()).toContain('每次增减 1 分')
  expect(wrapper.get('.frozen-questionnaire').text()).toContain('不计分')
  expect(wrapper.get('.frozen-questionnaire').findAll('input, textarea')).toHaveLength(0)
})

it('已完成项目保持历史人员，筛选不查询候选或修改配置', async () => {
  const value = config('COMPLETED')
  const original = JSON.stringify(value)
  await open(value)
  expect(wrapper.text()).toContain('已完成')
  expect(wrapper.findAll('button').some(button => button.text() === '查看评价进度')).toBe(false)
  await tab('人员安排')
  expect(wrapper.text()).toContain('发布时李四')
  expect(wrapper.text()).not.toContain('可选评价人')
  expect(wrapper.text()).not.toContain('失效')
  const input = wrapper.get('.people-filter input')
  await input.setValue('原部门')
  await input.trigger('keydown', { key: 'Enter' })
  await flushPromises()
  expect(wrapper.text()).toContain('发布时李四')
  await input.setValue('不存在')
  const event = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true })
  input.element.dispatchEvent(event)
  await flushPromises()
  expect(event.defaultPrevented).toBe(true)
  expect(wrapper.text()).toContain('没有匹配的人员安排')
  expect(JSON.stringify(value)).toBe(original)
})

it('仅自评规则及缺少冻结详情的降级均有明确说明', async () => {
  const value = config()
  value.targets[0].onlySelfEvaluation = true
  value.relations = value.relations.slice(0, 1)
  value.frozenDetails = null
  await open(value)
  expect(wrapper.text()).toContain('发布详情暂未加载完整')
  await tab('评价规则')
  expect(wrapper.text()).toContain('本轮仅自评，按每人的自评结果计分。')
})
