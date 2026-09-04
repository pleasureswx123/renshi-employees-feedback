import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const getQuestionnaireDraft = vi.fn()
const saveQuestionnaireDraft = vi.fn()
vi.mock('@/api/feedback/projects', () => ({ getQuestionnaireDraft, saveQuestionnaireDraft }))

const { useQuestionnaireDraftStore } = await import('@/stores/questionnaireDraft')

function emptyDraft() {
  return {
    projectId: 7,
    projectName: 'P4测试项目',
    projectStatus: 'PREPARING',
    versionId: 9,
    versionNo: 1,
    versionStatus: 'DRAFT',
    lockVersion: 0,
    title: 'P4测试问卷',
    description: '',
    descriptionDoc: { type: 'doc', content: [{ type: 'paragraph' }] },
    settings: {},
    pages: [{ pageId: 11, pageCode: 'P_1', pageTitle: '第1页', sortOrder: 1, questions: [] }],
    indicators: [],
    validationIssues: [],
    isPublishReady: false
  }
}

describe('问卷草稿Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getQuestionnaireDraft.mockReset()
    saveQuestionnaireDraft.mockReset()
  })

  it('加载、添加单选题、保存并采用后端返回版本', async () => {
    getQuestionnaireDraft.mockResolvedValue({ data: emptyDraft() })
    const store = useQuestionnaireDraftStore()
    await store.load(7)

    store.addSingleChoice()
    expect(store.dirty).toBe(true)
    expect(store.selectedQuestion.questionType).toBe('SINGLE_CHOICE')
    expect(store.selectedQuestion.options).toHaveLength(2)
    store.updateQuestion({ ...store.selectedQuestion, title: '协作是否顺畅？' })

    const savedDraft = JSON.parse(JSON.stringify(store.draft))
    savedDraft.lockVersion = 1
    savedDraft.pages[0].questions[0].questionId = 100
    saveQuestionnaireDraft.mockResolvedValue({ data: savedDraft })

    await store.save()

    expect(saveQuestionnaireDraft).toHaveBeenCalledWith(
      7,
      expect.objectContaining({ versionId: 9, lockVersion: 0, title: 'P4测试问卷' })
    )
    expect(store.draft.lockVersion).toBe(1)
    expect(store.dirty).toBe(false)
    expect(store.lastSavedAt).toBeInstanceOf(Date)
  })

  it('加载历史草稿及新增分页均只保留问卷说明，保存不再发送页面说明', async () => {
    const draft = emptyDraft()
    draft.description = '统一问卷说明'
    draft.descriptionDoc = { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: draft.description }] }] }
    draft.pages[0].pageDescription = '历史页面说明'
    getQuestionnaireDraft.mockResolvedValue({ data: draft })
    const store = useQuestionnaireDraftStore()
    await store.load(7)

    expect(store.draft.pages[0]).not.toHaveProperty('pageDescription')
    expect(store.addPage()).not.toHaveProperty('pageDescription')
    // 即使旧客户端内存残留该字段，保存契约也不会将其重新写回。
    store.draft.pages[0].pageDescription = '旧内存残留'
    saveQuestionnaireDraft.mockImplementation(async (_, payload) => ({
      data: { ...draft, ...payload, lockVersion: 1 }
    }))
    await store.save()

    const payload = saveQuestionnaireDraft.mock.calls[0][1]
    expect(payload.pages).toHaveLength(2)
    expect(payload.pages.every(page => !Object.hasOwn(page, 'pageDescription'))).toBe(true)
    expect(store.draft.pages.every(page => !Object.hasOwn(page, 'pageDescription'))).toBe(true)
    expect(store.draft.description).toBe('统一问卷说明')
    expect(store.draft.descriptionDoc).toEqual(draft.descriptionDoc)
    expect(store.draft.pages.map(page => page.pageTitle)).toEqual(['第1页', '第2页'])
  })

  it('保存前拒绝空标题和不足两个选项', async () => {
    getQuestionnaireDraft.mockResolvedValue({ data: emptyDraft() })
    const store = useQuestionnaireDraftStore()
    await store.load(7)
    store.addSingleChoice()
    store.draft.title = '  '
    store.selectedQuestion.options.splice(1)

    await expect(store.save()).rejects.toThrow('请填写问卷标题')
    expect(saveQuestionnaireDraft).not.toHaveBeenCalled()
  })

  it('复制题目时生成全新稳定标识，并支持上下排序', async () => {
    getQuestionnaireDraft.mockResolvedValue({ data: emptyDraft() })
    const store = useQuestionnaireDraftStore()
    await store.load(7)
    store.addSingleChoice()
    store.selectedQuestion.questionId = 100
    store.selectedQuestion.title = '协作是否顺畅？'
    store.selectedQuestion.options[0].optionId = 201
    store.selectedQuestion.options[1].optionId = 202
    const originalQuestionCode = store.selectedQuestion.questionCode
    const originalOptionCodes = store.selectedQuestion.options.map(option => option.optionCode)

    store.duplicateSelectedQuestion()

    expect(store.draft.pages[0].questions).toHaveLength(2)
    expect(store.selectedQuestion.questionId).toBeNull()
    expect(store.selectedQuestion.questionCode).not.toBe(originalQuestionCode)
    expect(store.selectedQuestion.title).toBe('协作是否顺畅？（副本）')
    expect(store.selectedQuestion.options.every(option => option.optionId === null)).toBe(true)
    expect(store.selectedQuestion.options.map(option => option.optionCode)).not.toEqual(originalOptionCodes)
    expect(store.draft.pages[0].questions.map(question => question.sortOrder)).toEqual([1, 2])

    store.moveSelectedQuestion(-1)
    expect(store.draft.pages[0].questions[0].questionCode).toBe(store.selectedQuestionCode)
    expect(store.draft.pages[0].questions.map(question => question.sortOrder)).toEqual([1, 2])

    store.moveSelectedQuestion(1)
    expect(store.draft.pages[0].questions[1].questionCode).toBe(store.selectedQuestionCode)
    expect(store.dirty).toBe(true)
  })

  it('支持多页、五题型、跨页移动和稳定code选择恢复', async () => {
    getQuestionnaireDraft.mockResolvedValue({ data: emptyDraft() })
    const store = useQuestionnaireDraftStore()
    await store.load(7)

    for (const type of ['SINGLE_CHOICE', 'STAR_RATING', 'NUMERIC_INPUT', 'SLIDER', 'TEXT']) {
      store.addQuestion(type)
      store.updateQuestion({ ...store.selectedQuestion, title: '请评价近期工作表现' })
    }
    expect(store.draft.pages[0].questions.map(item => item.questionType)).toEqual([
      'SINGLE_CHOICE',
      'STAR_RATING',
      'NUMERIC_INPUT',
      'SLIDER',
      'TEXT'
    ])

    const selectedCode = store.selectedQuestionCode
    const secondPage = store.addPage()
    store.selectQuestion(selectedCode)
    store.moveSelectedQuestionToPage(secondPage.pageCode)
    expect(store.draft.pages[1].questions[0].questionCode).toBe(selectedCode)
    expect(store.draft.pages.map(page => page.sortOrder)).toEqual([1, 2])

    const savedDraft = JSON.parse(JSON.stringify(store.draft))
    savedDraft.lockVersion = 1
    savedDraft.pages[1].pageId = 12
    savedDraft.pages[1].questions[0].questionId = 100
    saveQuestionnaireDraft.mockResolvedValue({ data: savedDraft })
    await store.save()

    expect(store.selectedPageCode).toBe(secondPage.pageCode)
    expect(store.selectedQuestionCode).toBe(selectedCode)
    expect(store.selectedQuestion.questionId).toBe(100)
    expect(saveQuestionnaireDraft.mock.calls[0][1].pages).toHaveLength(2)
  })

  it('新题与空内容副本不能依靠默认名称绕过保存校验', async () => {
    getQuestionnaireDraft.mockResolvedValue({ data: emptyDraft() })
    const store = useQuestionnaireDraftStore()
    await store.load(7)
    store.addSingleChoice()
    expect(store.selectedQuestion.title).toBe('')
    store.updateQuestion({ ...store.selectedQuestion, title: '   ' })
    store.duplicateSelectedQuestion()
    expect(store.selectedQuestion.title).toBe('')
    await expect(store.save()).rejects.toThrow('请填写题目内容')
    expect(saveQuestionnaireDraft).not.toHaveBeenCalled()
  })

  it('维护指标绑定唯一性，并在删题时移除悬空绑定', async () => {
    getQuestionnaireDraft.mockResolvedValue({ data: emptyDraft() })
    const store = useQuestionnaireDraftStore()
    await store.load(7)
    const firstQuestion = store.addQuestion('STAR_RATING')
    const secondQuestion = store.addQuestion('NUMERIC_INPUT')
    const firstIndicator = store.addIndicator()
    const secondIndicator = store.addIndicator()

    store.setIndicatorBindings(firstIndicator.indicatorCode, [firstQuestion.questionCode, secondQuestion.questionCode])
    store.setQuestionIndicator(secondQuestion.questionCode, secondIndicator.indicatorCode)
    expect(firstIndicator.questionCodes).toEqual([firstQuestion.questionCode])
    expect(secondIndicator.questionCodes).toEqual([secondQuestion.questionCode])

    store.selectQuestion(secondQuestion.questionCode)
    store.removeSelectedQuestion()
    expect(secondIndicator.questionCodes).toEqual([])
    expect(store.draft.pages[0].questions.map(item => item.sortOrder)).toEqual([1])
  })
})
