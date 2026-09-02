import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const getQuestionnaireDraft = vi.fn()
const saveQuestionnaireDraft = vi.fn()
vi.mock('@/api/feedback/projects', () => ({ getQuestionnaireDraft, saveQuestionnaireDraft }))

const { useQuestionnaireDraftStore } = await import('@/stores/questionnaireDraft')

function emptyDraft() {
  return {
    projectId: 7,
    projectName: 'P3测试项目',
    projectStatus: 'PREPARING',
    versionId: 9,
    versionNo: 1,
    versionStatus: 'DRAFT',
    lockVersion: 0,
    title: 'P3测试问卷',
    description: '',
    settings: {},
    pages: [{ pageId: 11, pageTitle: '第1页', sortOrder: 1, questions: [] }]
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

    const savedDraft = JSON.parse(JSON.stringify(store.draft))
    savedDraft.lockVersion = 1
    savedDraft.pages[0].questions[0].questionId = 100
    saveQuestionnaireDraft.mockResolvedValue({ data: savedDraft })

    await store.save()

    expect(saveQuestionnaireDraft).toHaveBeenCalledWith(
      7,
      expect.objectContaining({ versionId: 9, lockVersion: 0, title: 'P3测试问卷' })
    )
    expect(store.draft.lockVersion).toBe(1)
    expect(store.dirty).toBe(false)
    expect(store.lastSavedAt).toBeInstanceOf(Date)
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
    store.selectedQuestion.options[0].optionId = 201
    store.selectedQuestion.options[1].optionId = 202
    const originalQuestionCode = store.selectedQuestion.questionCode
    const originalOptionCodes = store.selectedQuestion.options.map(option => option.optionCode)

    store.duplicateSelectedQuestion()

    expect(store.draft.pages[0].questions).toHaveLength(2)
    expect(store.selectedQuestion.questionId).toBeNull()
    expect(store.selectedQuestion.questionCode).not.toBe(originalQuestionCode)
    expect(store.selectedQuestion.title).toBe('新的单选题（副本）')
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
})
