import ElementPlus, { ElMessage, ElMessageBox } from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, RouterView } from 'vue-router'
import { DOMWrapper, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import QuestionnaireEditorView from '@/views/hr/QuestionnaireEditorView.vue'
import { getQuestionTypeDefinition } from '@/components/feedback/questions/questionTypeRegistry'
import { useQuestionnaireDraftStore } from '@/stores/questionnaireDraft'
import { useAuthStore } from '@/stores/auth'

const api = vi.hoisted(() => ({ getQuestionnaireDraft: vi.fn(), saveQuestionnaireDraft: vi.fn() }))
vi.mock('@/api/feedback/projects', () => api)

let wrapper
let store
let persisted
let router
const activeCard = () => wrapper.get('.question-card.active')
const button = name => {
  const scope = ['复制题目', '上移题目', '下移题目', '删除题目'].includes(name) ? activeCard() : wrapper
  return scope.findAll('button').find(item => item.text() === name || item.attributes('aria-label') === name)
}

function draftFixture() {
  const questions = ['SINGLE_CHOICE', 'STAR_RATING', 'NUMERIC_INPUT', 'SLIDER', 'TEXT'].map((type, index) => ({
    ...getQuestionTypeDefinition(type).createDefault(), isRequired: false, title: `工作表现评价 ${index + 1}`, questionCode: `Q${index + 1}`, questionId: index + 1
  }))
  return {
    projectId: 7, projectName: '画布编辑测试', projectStatus: 'PREPARING',
    versionId: 9, versionNo: 1, versionStatus: 'DRAFT', lockVersion: 0,
    title: '评价问卷', description: '', descriptionDoc: { type: 'doc', content: [{ type: 'paragraph' }] }, settings: {},
    pages: [
      { pageId: 11, pageCode: 'P1', pageTitle: '第一页', sortOrder: 1, questions: questions.slice(0, 2) },
      { pageId: 12, pageCode: 'P2', pageTitle: '第二页', sortOrder: 2, questions: questions.slice(2) }
    ],
    indicators: [{ indicatorId: 1, indicatorCode: 'I1', indicatorName: '协作', weight: '100.0000', sortOrder: 1, questionCodes: ['Q1'] }],
    validationIssues: [], isPublishReady: false
  }
}

async function selectQuestion(code) {
  store.selectQuestion(code)
  await flushPromises()
}

async function switchRightTab(name) {
  await wrapper.findAll('[role="tab"]').find(item => item.text() === name).trigger('click')
  await flushPromises()
}

async function changeNumber(scope, label, value) {
  const field = scope.findAllComponents({ name: 'ElFormItem' }).find(item => item.props('label') === label)
  const input = field.get('input')
  await input.setValue(value)
  await flushPromises()
}

describe('问卷画布直接编辑', () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    const pinia = createPinia()
    setActivePinia(pinia)
    useAuthStore().permissions = ['feedback:questionnaire:edit']
    persisted = draftFixture()
    api.getQuestionnaireDraft.mockImplementation(async () => ({ data: structuredClone(persisted) }))
    api.saveQuestionnaireDraft.mockImplementation(async (_, payload) => {
      persisted = { ...persisted, ...structuredClone(payload), lockVersion: payload.lockVersion + 1 }
      return { data: structuredClone(persisted) }
    })
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm')
    Element.prototype.scrollIntoView = vi.fn()
    router = createRouter({ history: createMemoryHistory(), routes: [
      { path: '/hr/projects/:projectId/editor', component: QuestionnaireEditorView },
      { path: '/hr/projects/:projectId/publication', component: { template: '<div>人员配置</div>' } }
    ] })
    await router.push('/hr/projects/7/editor')
    wrapper = mount(RouterView, { attachTo: document.body, global: { plugins: [pinia, router, ElementPlus] } })
    await flushPromises()
    store = useQuestionnaireDraftStore()
  })

  afterEach(() => { wrapper?.unmount(); ElMessage.closeAll(); document.body.innerHTML = '' })

  it('顺序进入指标步骤，未绑定题目时留在当前页且不发送保存', async () => {
    useAuthStore().permissions.push('feedback:participant:manage')
    expect(wrapper.get('.editor-workflow').text()).toContain('1 编辑问卷')
    expect(wrapper.get('.editor-workflow').text()).toContain('3 人员与发布')
    expect(wrapper.find('.properties-panel').text()).not.toContain('先在“评价指标”中添加指标')
    await button('下一步：配置指标').trigger('click')
    await flushPromises()
    expect(wrapper.get('#tab-indicator').attributes('aria-selected')).toBe('true')
    expect(wrapper.get('.indicator-step-notice').text()).toContain('还有3道计分题未绑定指标')
    await button('下一步：配置人员').trigger('click')
    await flushPromises()
    expect(api.saveQuestionnaireDraft).not.toHaveBeenCalled()
    expect(router.currentRoute.value.path).toBe('/hr/projects/7/editor')
  })

  it('问卷未完成时下一步定位空题，完成后才进入指标', async () => {
    store.draft.pages[1].questions[2].title = ''
    await flushPromises()
    await button('完善问卷').trigger('click')
    await flushPromises()
    expect(wrapper.get('#tab-question').attributes('aria-selected')).toBe('true')
    expect(store.selectedQuestionCode).toBe('Q5')
    expect(api.saveQuestionnaireDraft).not.toHaveBeenCalled()
    await activeCard().get('.title-field textarea').setValue('改进建议')
    await button('下一步：配置指标').trigger('click')
    await flushPromises()
    expect(wrapper.get('#tab-indicator').attributes('aria-selected')).toBe('true')
  })

  it('配置指标后新增题目，按钮和步骤回到问卷，补完后保留指标并提示绑定新题', async () => {
    useAuthStore().permissions.push('feedback:participant:manage')
    store.setIndicatorBindings('I1', ['Q1', 'Q2', 'Q3', 'Q4'])
    await button('下一步：配置指标').trigger('click')
    expect(button('下一步：配置人员')).toBeDefined()
    await wrapper.findAll('.question-type-button').find(item => item.text() === '单选题').trigger('click')
    await flushPromises()
    const addedCode = store.selectedQuestionCode
    expect(wrapper.get('#tab-question').attributes('aria-selected')).toBe('true')
    expect(button('完善问卷')).toBeDefined()
    expect(button('下一步：配置人员')).toBeUndefined()
    expect(wrapper.findComponent({ name: 'ElSteps' }).props('active')).toBe(0)
    await switchRightTab('评价指标')
    expect(button('完善问卷')).toBeDefined()
    expect(button('下一步：配置人员')).toBeUndefined()
    expect(wrapper.findComponent({ name: 'ElSteps' }).props('active')).toBe(0)
    expect(wrapper.get('.indicator-step-notice').text()).toContain('已有指标配置会保留')
    await button('完善问卷').trigger('click')
    await flushPromises()
    expect(document.activeElement).toBe(activeCard().get('.title-field textarea').element)
    expect(store.selectedQuestionCode).toBe(addedCode)
    await activeCard().get('.title-field textarea').setValue('新增协作题')
    await button('下一步：配置指标').trigger('click')
    await flushPromises()
    expect(wrapper.get('.indicator-step-notice').text()).toContain('还有1道计分题未绑定指标')
    expect(store.draft.indicators[0]).toMatchObject({ indicatorName: '协作', weight: '100.0000', questionCodes: ['Q1', 'Q2', 'Q3', 'Q4'] })
    expect(wrapper.findComponent({ name: 'ElSteps' }).props('active')).toBe(1)
    expect(api.saveQuestionnaireDraft).not.toHaveBeenCalled()
  })

  it('指标页签内清空题目时也能返回完善问卷，不受人员配置权限限制', async () => {
    await button('下一步：配置指标').trigger('click')
    expect(button('下一步：配置人员')).toBeUndefined()
    await activeCard().get('.title-field textarea').setValue('')
    expect(button('完善问卷')).toBeDefined()
    expect(wrapper.findComponent({ name: 'ElSteps' }).props('active')).toBe(0)
    await button('完善问卷').trigger('click')
    await flushPromises()
    expect(wrapper.get('#tab-question').attributes('aria-selected')).toBe('true')
    expect(document.activeElement).toBe(activeCard().get('.title-field textarea').element)
    expect(api.saveQuestionnaireDraft).not.toHaveBeenCalled()
  })

  it('保存草稿允许指标未完成；下一步服从后端完整性检查并展示问题', async () => {
    useAuthStore().permissions.push('feedback:participant:manage')
    await button('保存草稿').trigger('click')
    await flushPromises()
    expect(api.saveQuestionnaireDraft).toHaveBeenCalledOnce()
    store.setIndicatorBindings('I1', ['Q1', 'Q2', 'Q3', 'Q4'])
    persisted.validationIssues = [{ code: 'CHECK_FAILED', path: 'indicators', message: '请核对指标配置' }]
    await button('下一步：配置指标').trigger('click')
    await button('下一步：配置人员').trigger('click')
    await flushPromises()
    expect(api.saveQuestionnaireDraft).toHaveBeenCalledTimes(2)
    expect(router.currentRoute.value.path).toBe('/hr/projects/7/editor')
    expect(wrapper.get('.indicator-step-notice').text()).toContain('请核对指标配置')
  })

  it('下一步保存失败保留本页草稿，重试成功后进入人员配置', async () => {
    useAuthStore().permissions.push('feedback:participant:manage')
    store.setIndicatorBindings('I1', ['Q1', 'Q2', 'Q3', 'Q4'])
    api.saveQuestionnaireDraft.mockRejectedValueOnce(new Error('保存失败，请重试'))
    await button('下一步：配置指标').trigger('click')
    await button('下一步：配置人员').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/hr/projects/7/editor')
    expect(store.dirty).toBe(true)
    expect(store.draft.indicators[0].questionCodes).toEqual(['Q1', 'Q2', 'Q3', 'Q4'])
    persisted.isPublishReady = true
    await button('下一步：配置人员').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/hr/projects/7/publication')
    expect(ElMessageBox.confirm).not.toHaveBeenCalled()
  })

  it('下一步等待保存时禁止重复提交和编辑；无人员权限不显示人员入口', async () => {
    store.setIndicatorBindings('I1', ['Q1', 'Q2', 'Q3', 'Q4'])
    await button('下一步：配置指标').trigger('click')
    expect(button('下一步：配置人员')).toBeUndefined()
    useAuthStore().permissions.push('feedback:participant:manage')
    await flushPromises()
    let finishSave
    api.saveQuestionnaireDraft.mockImplementation(() => new Promise(resolve => { finishSave = resolve }))
    await button('下一步：配置人员').trigger('click')
    await flushPromises()
    expect(wrapper.get('.editor-grid').attributes('inert')).toBeDefined()
    await button('下一步：配置人员').trigger('click')
    expect(api.saveQuestionnaireDraft).toHaveBeenCalledOnce()
    finishSave({ data: { ...persisted, isPublishReady: true } })
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/hr/projects/7/publication')
  })

  it('待绑定清单展示连续题号与页码，可定位、直接绑定并在保存重载后保留', async () => {
    await switchRightTab('评价指标')
    const items = () => wrapper.findAll('.unbound-item')
    expect(items()).toHaveLength(3)
    expect(items()[0].text()).toContain('第 2 题')
    expect(items()[0].text()).toContain('第 1 页')
    expect(items()[1].text()).toContain('第 3 题')
    expect(items()[1].text()).toContain('第 2 页')
    expect(wrapper.get('.unbound-panel').text()).not.toContain('工作表现评价 5')
    await items()[1].get('button').trigger('click')
    await flushPromises()
    expect(store.selectedQuestionCode).toBe('Q3')
    expect(wrapper.get('#tab-indicator').attributes('aria-selected')).toBe('true')
    for (const item of items()) {
      item.findComponent({ name: 'ElSelect' }).vm.$emit('change', 'I1')
    }
    await flushPromises()
    expect(wrapper.find('.unbound-panel').exists()).toBe(false)
    expect(wrapper.get('.binding-complete').text()).toBe('计分题已全部绑定')
    expect(store.draft.indicators[0].questionCodes).toEqual(['Q1', 'Q2', 'Q3', 'Q4'])
    expect(store.dirty).toBe(true)
    expect(api.saveQuestionnaireDraft).not.toHaveBeenCalled()
    await button('保存草稿').trigger('click')
    await flushPromises()
    await store.load(7)
    await flushPromises()
    expect(wrapper.find('.unbound-panel').exists()).toBe(false)
    expect(store.draft.indicators[0].questionCodes).toEqual(['Q1', 'Q2', 'Q3', 'Q4'])
    store.setIndicatorBindings('I1', ['Q1', 'Q2', 'Q4'])
    await flushPromises()
    expect(items()).toHaveLength(1)
    expect(items()[0].text()).toContain('工作表现评价 3')
    store.removeIndicator('I1')
    await flushPromises()
    expect(items()).toHaveLength(4)
    expect(wrapper.get('.unbound-hint').text()).toContain('先增加指标')
    expect(items()[0].findComponent({ name: 'ElSelect' }).props('disabled')).toBe(true)
  })

  it('待绑定清单随页面重排和计分开关更新，不把问答题或不计分题列入', async () => {
    store.draft.pages[0].questions[1].isScored = false
    await switchRightTab('评价指标')
    expect(wrapper.findAll('.unbound-item')).toHaveLength(2)
    store.movePage('P2', -1)
    await flushPromises()
    const items = wrapper.findAll('.unbound-item')
    expect(items[0].text()).toContain('第 1 题')
    expect(items[0].text()).toContain('第 1 页')
    expect(items[0].text()).toContain('工作表现评价 3')
    expect(items[1].text()).toContain('第 2 题')
    expect(wrapper.get('.unbound-panel').text()).not.toContain('工作表现评价 2')
    expect(wrapper.get('.unbound-panel').text()).not.toContain('工作表现评价 5')
  })

  it('默认显示题目属性，往返切换页签保留当前题目与预览试填', async () => {
    const tab = name => wrapper.findAll('[role="tab"]').find(item => item.text() === name)
    expect(tab('题目属性').attributes('aria-selected')).toBe('true')
    await switchRightTab('实时预览')
    expect(tab('实时预览').attributes('aria-selected')).toBe('true')
    await wrapper.get('#pane-preview .el-radio input').setValue(true)
    await switchRightTab('题目属性')
    expect(store.selectedQuestionCode).toBe('Q1')
    await switchRightTab('评价指标')
    await switchRightTab('实时预览')
    expect(wrapper.get('#pane-preview .el-radio input').element.checked).toBe(true)
    expect(store.dirty).toBe(false)
    expect(api.saveQuestionnaireDraft).not.toHaveBeenCalled()
  })

  it('五题型用独立标识和内容示例引导，新题留空并在大纲提示待填写', async () => {
    const content = [
      ['单选题', '他/她能否及时响应团队协作需求？', '能否按时完成协作任务？'],
      ['星级评分', '请评价他/她的团队协作表现', '请评价沟通的及时性'],
      ['数字输入', '请为他/她的工作完成质量打分', '请为工作质量评分'],
      ['滑动评分', '请评价他/她主动承担工作的程度', '请评价主动承担工作的程度'],
      ['问答题', '你认为他/她最值得保持的优点是什么？', '你最认可他/她的哪项优点？']
    ]
    for (const [typeLabel, example, title] of content) {
      const addButton = wrapper.findAll('.question-type-button').find(item => item.text() === typeLabel)
      await addButton.trigger('click')
      await flushPromises()
      const card = activeCard()
      const field = card.get('.title-field textarea')
      expect(card.get('.question-type-badge').text()).toBe(typeLabel)
      expect(card.get('.question-type-badge svg').exists()).toBe(true)
      expect(card.get('.title-field .el-form-item__label').text()).toBe('题目内容')
      expect(field.element.value).toBe('')
      expect(store.selectedQuestion.isRequired).toBe(true)
      expect(card.get('.required-hint').text()).toBe('必答')
      expect(wrapper.get('.properties-panel [role="switch"]').attributes('aria-checked')).toBe('true')
      expect(field.attributes('placeholder')).toBe(`例如：${example}`)
      expect(document.activeElement).toBe(field.element)
      expect(wrapper.get('.outline-question.active').text()).toContain(`${typeLabel} · 待填写`)
      if (typeLabel === '单选题') {
        await wrapper.findAll('[role="tab"]').find(item => item.text() === '评价指标').trigger('click')
        await flushPromises()
        expect(wrapper.get('.indicator-step-notice').text()).toContain('请先完成问卷，再配置指标')
        expect(wrapper.find('.indicator-panel').exists()).toBe(false)
        await wrapper.findAll('[role="tab"]').find(item => item.text() === '题目属性').trigger('click')
      }
      await field.setValue(title)
      expect(store.selectedQuestion.title).toBe(title)
      expect(wrapper.get('.outline-question.active').text()).toContain(title)
    }
    await button('保存草稿').trigger('click')
    await flushPromises()
    expect(api.saveQuestionnaireDraft).toHaveBeenCalledTimes(1)
    const savedQuestions = persisted.pages.flatMap(page => page.questions)
    for (const [, , title] of content) expect(savedQuestions.find(question => question.title === title)?.isRequired).toBe(true)
    expect(savedQuestions.every(question => !Object.hasOwn(question, 'contentPlaceholder'))).toBe(true)
  })

  it('在画布修改标题、说明、选项和分值，保存重载后完整恢复', async () => {
    const optionCode = store.selectedQuestion.options[0].optionCode
    await activeCard().get('.title-field textarea').setValue('协作是否顺畅？')
    await activeCard().get('.description-field textarea').setValue('请依据近期的实际协作经历')
    await activeCard().get('.option-label input').setValue('非常顺畅')
    await changeNumber(activeCard(), '选项 1 分值', '5')
    await activeCard().get('input[type="checkbox"]').setValue(true)
    await button('增加选项').trigger('click')
    expect(activeCard().findAll('.option-editor')).toHaveLength(3)
    expect(store.selectedQuestion.options[2].score).toBe('1.0000')
    await button('删除选项 3').trigger('click')
    expect(button('删除选项 1').element.disabled).toBe(true)
    expect(wrapper.get('.properties-panel').findAll('textarea')).toHaveLength(0)
    expect(wrapper.get('.canvas-summary').text()).toContain('120.0000')
    expect(button('1. 协作是否顺畅？')).toBeDefined()
    await button('保存草稿').trigger('click')
    await flushPromises()
    expect(api.saveQuestionnaireDraft).toHaveBeenCalledOnce()
    await store.load(7)
    await flushPromises()
    expect(store.selectedQuestion).toMatchObject({ title: '协作是否顺畅？', description: '请依据近期的实际协作经历' })
    expect(store.selectedQuestion.options[0]).toMatchObject({ optionCode, optionLabel: '非常顺畅', score: '5.0000', requiresReason: true })
    expect(activeCard().get('.title-field textarea').element.value).toBe('协作是否顺畅？')
  })

  it('实时预览同步内容与选项，可试填原因且不污染保存载荷', async () => {
    await switchRightTab('实时预览')
    const preview = () => wrapper.get('#pane-preview')
    await activeCard().get('.title-field textarea').setValue('协作是否顺畅？')
    await activeCard().get('.description-field textarea').setValue('请依据近期表现')
    await activeCard().get('.option-label input').setValue('非常顺畅')
    await activeCard().get('input[type="checkbox"]').setValue(true)
    expect(preview().get('.preview-question').text()).toContain('协作是否顺畅？')
    expect(preview().text()).toContain('请依据近期表现')
    expect(preview().text()).toContain('非常顺畅')
    await preview().get('.el-radio input').setValue(true)
    await preview().get('textarea[aria-label="附加原因"]').setValue('试填内容')
    await activeCard().get('.title-field textarea').setValue('协作是否及时？')
    expect(preview().get('textarea[aria-label="附加原因"]').element.value).toBe('试填内容')
    await button('保存草稿').trigger('click')
    await flushPromises()
    expect(JSON.stringify(api.saveQuestionnaireDraft.mock.calls[0][1])).not.toContain('试填内容')
    const dirtyBefore = store.dirty
    await button('重新试填').trigger('click')
    expect(preview().find('textarea[aria-label="附加原因"]').exists()).toBe(false)
    expect(store.dirty).toBe(dirtyBefore)
  })

  it('预览跟随当前页，参数修改清除失效试填，题目标题留空也能预览', async () => {
    await switchRightTab('实时预览')
    await selectQuestion('Q3')
    const preview = () => wrapper.get('#pane-preview')
    expect(preview().findAll('.preview-question')).toHaveLength(3)
    expect(preview().text()).not.toContain('工作表现评价 1')
    const question = () => preview().get('[data-question-code="Q3"]')
    await question().get('input[aria-label="数字评分"]').setValue('80')
    expect(question().get('input').element.value).toBe('80')
    await changeNumber(activeCard(), '最高分', '10')
    expect(store.selectedQuestion.maxScore).toBe('10.0000')
    expect(question().get('input').attributes('aria-valuemax')).toBe('10')
    expect(question().get('input').element.value).toBe('')
    await activeCard().get('.title-field textarea').setValue('')
    expect(question().text()).toContain('数字输入 · 待填写题目内容')
    expect(button('电脑 / 手机预览')).toBeUndefined()
    expect(api.saveQuestionnaireDraft).not.toHaveBeenCalled()
  })

  it('预览页码同步画布，切页回到问卷开头并保留标题、说明和各页试填', async () => {
    await switchRightTab('实时预览')
    store.draft.descriptionDoc = { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: '请依据近期工作表现作答' }] }] }
    await flushPromises()
    const preview = () => wrapper.get('#pane-preview')
    const switchPage = async number => {
      await preview().findAll('.live-preview-pagination .number').find(item => item.text() === String(number)).trigger('click')
      await flushPromises()
    }
    const expectHeader = () => {
      expect(preview().get('.preview-document-heading h2').text()).toBe('评价问卷')
      expect(preview().get('.preview-document-heading').text()).toContain('请依据近期工作表现作答')
      expect(preview().find('.preview-page > h3').exists()).toBe(false)
    }
    await preview().get('.el-radio input').setValue(true)
    wrapper.get('.right-panel .el-tabs__content').element.scrollTop = 160
    await switchPage(2)
    expect(store.selectedPageCode).toBe('P2')
    expect(wrapper.findAll('.question-card')).toHaveLength(3)
    expect(wrapper.get('.right-panel .el-tabs__content').element.scrollTop).toBe(0)
    expect(preview().get('.live-preview-toolbar').text()).toContain('第 2 / 2 页')
    expectHeader()
    await preview().get('[data-question-code="Q3"] input').setValue('80')
    await switchPage(1)
    expectHeader()
    expect(preview().get('.el-radio input').element.checked).toBe(true)
    await switchPage(2)
    expect(preview().get('[data-question-code="Q3"] input').element.value).toBe('80')
    expect(store.dirty).toBe(false)
    expect(api.saveQuestionnaireDraft).not.toHaveBeenCalled()
    wrapper.get('.right-panel .el-tabs__content').element.scrollTop = 160
    store.addPage()
    await flushPromises()
    expectHeader()
    expect(preview().findAll('.preview-question')).toHaveLength(0)
    expect(wrapper.get('.right-panel .el-tabs__content').element.scrollTop).toBe(0)
    store.removePage(store.selectedPageCode)
    await flushPromises()
    expect(preview().get('.live-preview-toolbar').text()).toContain('/ 2 页')
    expectHeader()
  })

  it('大纲、画布与预览跨页连续编号，重排、跨页移动、增删和空白页不留断号', async () => {
    await switchRightTab('实时预览')
    await selectQuestion('Q3')
    const expectVisibleNumbers = numbers => {
      expect(wrapper.findAll('.question-index > span:first-child').map(item => item.text())).toEqual(numbers.map(number => `第 ${number} 题`))
      expect(wrapper.findAll('.preview-question-number').map(item => item.text())).toEqual(numbers.map(number => `${number}、`))
    }
    expectVisibleNumbers([3, 4, 5])
    expect(wrapper.get('.outline-question.active').text()).toBe('3. 工作表现评价 3')
    expect(store.dirty).toBe(false)

    store.movePage('P2', -1)
    await flushPromises()
    expectVisibleNumbers([1, 2, 3])
    expect(wrapper.findAll('.outline-question').map(item => item.text())).toEqual([
      '1. 工作表现评价 3', '2. 工作表现评价 4', '3. 工作表现评价 5', '4. 工作表现评价 1', '5. 工作表现评价 2'
    ])
    store.movePage('P2', 1)
    await selectQuestion('Q1')
    store.moveSelectedQuestionToPage('P2')
    await flushPromises()
    expectVisibleNumbers([2, 3, 4, 5])
    expect(wrapper.get('.outline-question.active').text()).toBe('5. 工作表现评价 1')

    store.removeSelectedQuestion()
    await flushPromises()
    expectVisibleNumbers([2, 3, 4])
    store.addPage()
    store.movePage(store.selectedPageCode, -1)
    await selectQuestion('Q3')
    expectVisibleNumbers([2, 3, 4])
    store.duplicateSelectedQuestion()
    await flushPromises()
    expectVisibleNumbers([2, 3, 4, 5])
    expect(wrapper.get('.outline-question.active').text()).toBe('3. 工作表现评价 3（副本）')
    expect(wrapper.findAll('.outline-question').map(item => Number(item.text().split('.')[0]))).toEqual([1, 2, 3, 4, 5])
    // 连续题号只用于展示，存储中的题目顺序仍属于各自页面。
    expect(store.draft.pages.map(page => page.questions.map(question => question.sortOrder))).toEqual([[1], [], [1, 2, 3, 4]])
    expect(api.saveQuestionnaireDraft).not.toHaveBeenCalled()
  })

  it.each(['0.0000', '4.5000'])('打开历史%s分选项时提示重新设置，不隐式改写草稿', async score => {
    store.selectedQuestion.options[0].score = score
    await flushPromises()
    expect(store.selectedQuestion.options[0].score).toBe(score)
    expect(store.dirty).toBe(false)
    expect(activeCard().get('.option-score input').element.value).toBe('')
    await vi.waitFor(() => expect(activeCard().text()).toContain(`原分值为 ${score}`))
    await changeNumber(activeCard(), '选项 1 分值', '5')
    expect(store.selectedQuestion.options[0].score).toBe('5.0000')
    expect(store.dirty).toBe(true)
  })

  it.each(['0', '4.5'])('批量选项拒绝%s分并保留原选项，省略分值默认1分', async score => {
    const oldCodes = store.selectedQuestion.options.map(option => option.optionCode)
    await button('批量设置').trigger('click')
    await flushPromises()
    const dialog = new DOMWrapper(document.querySelector('[aria-label="批量设置选项"]'))
    await dialog.get('textarea').setValue(`较好 | ${score}\n一般 | 3`)
    await dialog.findAll('button').find(item => item.text() === '应用选项').trigger('click')
    await flushPromises()
    await vi.waitFor(() => expect(dialog.text()).toContain('第 1 行分值必须是'))
    expect(store.selectedQuestion.options.map(option => option.optionCode)).toEqual(oldCodes)
    await dialog.get('textarea').setValue('较好 | 5\n一般\n需改进 | ')
    await dialog.findAll('button').find(item => item.text() === '应用选项').trigger('click')
    await flushPromises()
    expect(store.selectedQuestion.options.map(option => option.score)).toEqual(['5.0000', '1.0000', '1.0000'])
  })

  it('图标操作保持复制独立标识、排序、当前选择与指标绑定', async () => {
    expect(button('上移题目').element.disabled).toBe(true)
    expect(button('下移题目').element.disabled).toBe(false)
    await button('复制题目').trigger('click')
    await flushPromises()
    const copyCode = store.selectedQuestionCode
    expect(copyCode).not.toBe('Q1')
    expect(store.selectedQuestion.options[0].optionCode).not.toBe(store.draft.pages[0].questions[0].options[0].optionCode)
    expect(store.draft.indicators[0].questionCodes).toEqual(['Q1'])
    await button('上移题目').trigger('click')
    await flushPromises()
    expect(store.draft.pages[0].questions[0].questionCode).toBe(copyCode)
    expect(button('上移题目').element.disabled).toBe(true)
    await button('下移题目').trigger('click')
    await flushPromises()
    expect(store.draft.pages[0].questions[1].questionCode).toBe(copyCode)
    ElMessageBox.confirm.mockRejectedValueOnce('cancel')
    await button('删除题目').trigger('click')
    await flushPromises()
    expect(store.draft.pages[0].questions).toHaveLength(3)
    await button('删除题目').trigger('click')
    await flushPromises()
    expect(store.draft.pages[0].questions.map(question => question.questionCode)).toEqual(['Q1', 'Q2'])
    expect(wrapper.findAll('.question-card.active .question-actions')).toHaveLength(1)
  })

  it('删除确认使用发起操作的题目，不误删随后切换的题目', async () => {
    let confirmDelete
    ElMessageBox.confirm.mockImplementation(() => new Promise(resolve => { confirmDelete = resolve }))
    await button('删除题目').trigger('click')
    await selectQuestion('Q2')
    confirmDelete('confirm')
    await flushPromises()
    expect(store.draft.pages[0].questions.map(question => question.questionCode)).toEqual(['Q2'])
    expect(store.draft.indicators[0].questionCodes).toEqual([])
  })

  it('五种题型的参数在画布更新，并保留原有定点数与范围契约', async () => {
    await selectQuestion('Q2')
    await changeNumber(activeCard(), '星级数量', '7')
    expect(store.selectedQuestion.maxScore).toBe('7.0000')
    expect(activeCard().findAll('.el-rate__item')).toHaveLength(7)
    await selectQuestion('Q3')
    await changeNumber(activeCard(), '最高分', '80')
    expect(store.selectedQuestion.maxScore).toBe('80.0000')
    await selectQuestion('Q4')
    await changeNumber(activeCard(), '滑动步长', '2')
    expect(store.selectedQuestion.config.step).toBe('2.0000')
    await selectQuestion('Q5')
    await changeNumber(activeCard(), '最大字数', '800')
    expect(store.selectedQuestion.config.maxLength).toBe(800)
    expect(store.selectedQuestion.isScored).toBe(false)
    expect(activeCard().get('textarea[aria-label="问答内容"]').attributes('maxlength')).toBe('800')
  })

  it('右侧规则与当前题目同步，跨页移动保留内容和指标绑定', async () => {
    await selectQuestion('Q2')
    await activeCard().get('.title-field textarea').setValue('协作星级')
    const panel = wrapper.get('.properties-panel')
    await panel.findAllComponents({ name: 'ElSwitch' })[0].trigger('click')
    expect(store.selectedQuestion.isRequired).toBe(true)
    expect(activeCard().text()).toContain('必答')
    expect(panel.findAllComponents({ name: 'ElFormItem' }).some(item => item.props('label') === '评价指标')).toBe(false)
    await switchRightTab('评价指标')
    wrapper.findComponent({ name: 'IndicatorPanel' }).vm.$emit('set-bindings', 'I1', ['Q1', 'Q2'])
    await flushPromises()
    expect(store.draft.indicators[0].questionCodes).toEqual(['Q1', 'Q2'])
    await switchRightTab('题目属性')
    const pageField = panel.findAllComponents({ name: 'ElFormItem' }).find(item => item.props('label') === '所在页面')
    pageField.findComponent({ name: 'ElSelect' }).vm.$emit('change', 'P2')
    await flushPromises()
    expect(store.selectedPageCode).toBe('P2')
    expect(store.selectedQuestionCode).toBe('Q2')
    expect(store.draft.pages[1].questions.at(-1)).toMatchObject({ title: '协作星级', isRequired: true })
    expect(store.draft.indicators[0].questionCodes).toEqual(['Q1', 'Q2'])
    expect(activeCard().get('.title-field textarea').element.value).toBe('协作星级')
  })

  it('输入框回车仅确认字段，保留题目文本换行和中文输入法行为', async () => {
    await selectQuestion('Q2')
    const input = activeCard().get('.question-settings input')
    const enter = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true })
    input.element.dispatchEvent(enter)
    expect(enter.defaultPrevented).toBe(true)
    const newline = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true })
    activeCard().get('.title-field textarea').element.dispatchEvent(newline)
    expect(newline.defaultPrevented).toBe(false)
    const composition = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true, isComposing: true })
    input.element.dispatchEvent(composition)
    expect(composition.defaultPrevented).toBe(false)
    expect(api.saveQuestionnaireDraft).not.toHaveBeenCalled()
  })

  it('页面标题在大纲重命名，校验空白并支持回车确认', async () => {
    expect(wrapper.get('.canvas-panel').text()).not.toContain('页面标题')
    await button('重命名页面：第一页').trigger('click')
    await flushPromises()
    const dialog = wrapper.findAllComponents({ name: 'ElDialog' }).find(item => item.props('title') === '重命名页面')
    const input = dialog.findComponent({ name: 'ElInput' }).get('input')
    await input.setValue('   ')
    await input.trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(store.draft.pages[0].pageTitle).toBe('第一页')
    await vi.waitFor(() => expect(document.body.textContent).toContain('请填写页面标题'))
    await input.setValue('协作评价')
    await input.trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(store.draft.pages[0].pageTitle).toBe('协作评价')
    expect(wrapper.get('.canvas-summary').text()).toContain('协作评价')
    expect(store.dirty).toBe(true)
  })

  it('保存校验定位其他页面的空题目，保存期间锁住编辑且不重复发送', async () => {
    store.draft.pages[1].questions[2].title = ''
    await button('保存草稿').trigger('click')
    await flushPromises()
    expect(api.saveQuestionnaireDraft).not.toHaveBeenCalled()
    expect(store.selectedQuestionCode).toBe('Q5')
    await vi.waitFor(() => expect(activeCard().text()).toContain('请填写题目内容'))
    await activeCard().get('.title-field textarea').setValue('改进建议')
    let finishSave
    api.saveQuestionnaireDraft.mockImplementation(() => new Promise(resolve => { finishSave = resolve }))
    await button('保存草稿').trigger('click')
    await flushPromises()
    expect(activeCard().get('.title-field textarea').element.disabled).toBe(true)
    expect(wrapper.get('.editor-grid').attributes('inert')).toBeDefined()
    await button('保存草稿').trigger('click')
    expect(api.saveQuestionnaireDraft).toHaveBeenCalledOnce()
    finishSave({ data: structuredClone(persisted) })
    await flushPromises()
    expect(wrapper.get('.editor-grid').attributes('inert')).toBeUndefined()
  })
})
