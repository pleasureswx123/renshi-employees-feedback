import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, RouterView } from 'vue-router'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import ProjectConfigurationView from '@/views/hr/ProjectConfigurationView.vue'
import { useQuestionnaireDraftStore } from '@/stores/questionnaireDraft'
import { useAuthStore } from '@/stores/auth'
import { getQuestionTypeDefinition } from '@/components/feedback/questions/questionTypeRegistry'

const api = vi.hoisted(() => ({ getQuestionnaireDraft: vi.fn(), saveQuestionnaireDraft: vi.fn(), getPublicationConfig: vi.fn(), savePublicationConfig: vi.fn(), getParticipantDepartments: vi.fn(), listParticipantOptions: vi.fn() }))
vi.mock('@/api/feedback/projects', () => api)
let wrapper, router, draft
beforeEach(async () => {
  vi.clearAllMocks()
  const pinia = createPinia()
  setActivePinia(pinia)
  useAuthStore().permissions = ['feedback:questionnaire:edit', 'feedback:participant:manage']
  const question = { ...getQuestionTypeDefinition('SINGLE_CHOICE').createDefault(), questionCode: 'Q1', title: '协作表现' }
  draft = { projectId: 7, projectName: '统一流程', versionId: 1, lockVersion: 0, title: '评价问卷', pages: [{ pageCode: 'P1', pageTitle: '第1页', questions: [question] }], indicators: [{ indicatorCode: 'I1', indicatorName: '协作', weight: '100', questionCodes: ['Q1'] }], validationIssues: [], isPublishReady: true }
  api.getQuestionnaireDraft.mockImplementation(async () => ({ data: structuredClone(draft) }))
  api.saveQuestionnaireDraft.mockImplementation(async (_, payload) => ({ data: structuredClone(draft = { ...draft, ...payload }) }))
  api.getPublicationConfig.mockResolvedValue({ data: { projectId: 7, projectName: '统一流程', editable: true, targets: [], relations: [], evaluatorSelections: [], configuredParticipants: [], validationIssues: [], isPublishReady: false } })
  api.getParticipantDepartments.mockResolvedValue({ data: [] })
  api.listParticipantOptions.mockResolvedValue({ rows: [], total: 0 })
  router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/hr/projects/:projectId/editor', component: ProjectConfigurationView }] })
  await router.push('/hr/projects/7/editor?step=1')
  wrapper = mount(RouterView, { global: { plugins: [pinia, router, ElementPlus] } })
  await flushPromises()
})
afterEach(() => wrapper?.unmount())
async function click(label) {
  const button = wrapper.findAll('button').find(item => item.text() === label && item.isVisible())
  expect(button).toBeTruthy()
  await button.trigger('click')
  await flushPromises()
}
it('问卷不显示指标页签，指标作为主内容，进入人员步骤保持相同页面及外壳', async () => {
  const shell = wrapper.get('.configuration-heading').element
  expect(wrapper.find('#tab-indicator').exists()).toBe(false)
  await click('下一步：配置指标与权重')
  expect(api.saveQuestionnaireDraft).toHaveBeenCalledOnce()
  expect(wrapper.get('.indicator-workspace').isVisible()).toBe(true)
  expect(wrapper.get('.editor-grid').isVisible()).toBe(false)
  expect(wrapper.get('.indicator-main').text()).toContain('权重（%）')
  expect(router.currentRoute.value.query.step).toBe('2')
  await click('下一步：评价谁')
  expect(router.currentRoute.value.path).toBe('/hr/projects/7/editor')
  expect(router.currentRoute.value.query.step).toBe('3')
  expect(wrapper.get('.configuration-heading').element).toBe(shell)
  expect(wrapper.get('.selector-panel').isVisible()).toBe(true)
  await wrapper.get('[aria-label="第2步：配置指标与权重"]').trigger('click')
  await flushPromises()
  expect(wrapper.get('.indicator-workspace').isVisible()).toBe(true)
})
it('保存失败停留问卷，不能通过URL跳过校验', async () => {
  api.saveQuestionnaireDraft.mockRejectedValueOnce(new Error('保存失败'))
  await click('下一步：配置指标与权重')
  expect(wrapper.find('.indicator-workspace').exists()).toBe(false)
  expect(router.currentRoute.value.query.step).toBe('1')
  await click('下一步：配置指标与权重')
  await click('下一步：评价谁')
  await router.replace({ query: { step: '6' } })
  await flushPromises()
  expect(router.currentRoute.value.query.step).toBe('3')
  expect(api.savePublicationConfig).not.toHaveBeenCalled()
})

it('只保留目录新增入口，缺少题目绑定时显示表单错误并阻止下一步', async () => {
  await click('下一步：配置指标与权重')
  expect(wrapper.findAll('button').filter(button => button.text().includes('增加指标'))).toHaveLength(1)
  const directoryItem = wrapper.get('.directory-item')
  await directoryItem.trigger('click')
  expect(directoryItem.attributes('aria-pressed')).toBe('true')
  const beforeCollapse = JSON.stringify(useQuestionnaireDraftStore().draft)
  expect(wrapper.get('.indicator-directory').classes()).toContain('left-panel')
  await wrapper.get('[aria-label="收起指标目录"]').trigger('click')
  expect(wrapper.get('.indicator-workspace').classes()).toContain('left-collapsed')
  expect(wrapper.get('[aria-label="展开指标目录"]').attributes('aria-expanded')).toBe('false')
  await wrapper.get('.indicator-directory [role="tab"]').trigger('click')
  expect(wrapper.get('.indicator-workspace').classes()).not.toContain('left-collapsed')
  expect(directoryItem.attributes('aria-pressed')).toBe('true')
  expect(JSON.stringify(useQuestionnaireDraftStore().draft)).toBe(beforeCollapse)
  useQuestionnaireDraftStore().setIndicatorBindings('I1', [])
  await flushPromises()
  await click('下一步：评价谁')
  await vi.waitFor(() => expect(wrapper.get('.indicator-main').text()).toContain('请至少绑定一道计分题'))
  expect(router.currentRoute.value.query.step).toBe('2')
  expect(api.saveQuestionnaireDraft).toHaveBeenCalledOnce()
})

it('绑定题目同步真实题型预览，试填不修改问卷配置', async () => {
  await click('下一步：配置指标与权重')
  const store = useQuestionnaireDraftStore()
  const second = { ...getQuestionTypeDefinition('SINGLE_CHOICE').createDefault(), questionCode: 'Q2', title: '第二道预览题' }
  store.draft.pages[0].questions.push(second)
  await flushPromises()
  const binding = wrapper.findAllComponents({ name: 'ElSelect' }).find(item => item.props('multiple'))
  binding.vm.$emit('change', ['Q1', 'Q2'])
  await flushPromises()
  const preview = wrapper.get('.indicator-reference')
  expect(preview.get('.preview-question.is-selected').attributes('data-question-code')).toBe('Q2')
  expect(preview.get('.preview-question.is-selected .preview-question-title').text()).toContain('2、')
  expect(preview.text()).toContain('第二道预览题')
  expect(preview.findAll('input[type="radio"]')).toHaveLength(4)
  expect(preview.get('.preview-document-heading').text()).toContain('评价问卷')
  expect(preview.find('[role="combobox"]').exists()).toBe(false)
  await preview.get('[aria-label="收起问卷预览"]').trigger('click')
  expect(wrapper.get('.indicator-workspace').classes()).toContain('right-collapsed')
  await preview.get('[aria-label="展开问卷预览"]').trigger('click')
  expect(preview.find('.properties-panel').exists()).toBe(false)
  const before = JSON.stringify(store.draft)
  await preview.findAll('input[type="radio"]')[0].setValue(true)
  expect(JSON.stringify(store.draft)).toBe(before)
})
