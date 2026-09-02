import { defineStore } from 'pinia'

import { getQuestionnaireDraft, saveQuestionnaireDraft } from '@/api/feedback/projects'
import { getQuestionTypeDefinition } from '@/components/feedback/questions/questionTypeRegistry'
import {
  createStableCode,
  normalizeQuestionnaireDraft,
  normalizeQuestionOrders,
  serializeQuestionnaireDraft,
  validateQuestionnaireDraft
} from '@/utils/questionnaireDraft'

function locateQuestion(draft, questionCode) {
  for (const page of draft?.pages || []) {
    const index = page.questions.findIndex(question => question.questionCode === questionCode)
    if (index >= 0) return { page, index, question: page.questions[index] }
  }
  return null
}

function duplicateQuestion(question) {
  const definition = getQuestionTypeDefinition(question.questionType)
  const duplicated = definition.clone(question)
  duplicated.questionId = null
  duplicated.questionCode = createStableCode('Q')
  duplicated.title = `${question.title.slice(0, 1996)}（副本）`
  duplicated.options = duplicated.options.map(option => ({
    ...option,
    optionId: null,
    optionCode: createStableCode('O')
  }))
  return duplicated
}

export const useQuestionnaireDraftStore = defineStore('questionnaireDraft', {
  state: () => ({
    projectId: null,
    draft: null,
    selectedPageCode: '',
    selectedQuestionCode: '',
    loading: false,
    saving: false,
    dirty: false,
    lastSavedAt: null
  }),
  getters: {
    selectedPage(state) {
      return state.draft?.pages.find(page => page.pageCode === state.selectedPageCode) || null
    },
    selectedQuestion(state) {
      return locateQuestion(state.draft, state.selectedQuestionCode)?.question || null
    },
    selectedQuestionPage(state) {
      return locateQuestion(state.draft, state.selectedQuestionCode)?.page || null
    },
    scoredQuestions(state) {
      return (state.draft?.pages || [])
        .flatMap(page => page.questions)
        .filter(question => question.isScored && question.questionType !== 'TEXT')
    }
  },
  actions: {
    async load(projectId) {
      if (this.loading) return
      this.loading = true
      try {
        const response = await getQuestionnaireDraft(projectId)
        this.projectId = Number(projectId)
        this.draft = normalizeQuestionnaireDraft(response.data)
        this.selectedPageCode = this.draft.pages[0]?.pageCode || ''
        this.selectedQuestionCode = this.draft.pages[0]?.questions[0]?.questionCode || ''
        this.dirty = false
        this.lastSavedAt = null
      } finally {
        this.loading = false
      }
    },
    markDirty() {
      this.dirty = true
    },
    selectPage(pageCode) {
      const page = this.draft?.pages.find(item => item.pageCode === pageCode)
      if (!page) return
      this.selectedPageCode = pageCode
      if (!page.questions.some(question => question.questionCode === this.selectedQuestionCode)) {
        this.selectedQuestionCode = page.questions[0]?.questionCode || ''
      }
    },
    selectQuestion(questionCode) {
      const located = locateQuestion(this.draft, questionCode)
      if (!located) return
      this.selectedPageCode = located.page.pageCode
      this.selectedQuestionCode = questionCode
    },
    addPage() {
      if (!this.draft || this.draft.pages.length >= 50) return
      const page = {
        pageId: null,
        pageCode: createStableCode('P'),
        pageTitle: `第${this.draft.pages.length + 1}页`,
        pageDescription: '',
        sortOrder: this.draft.pages.length + 1,
        questions: []
      }
      this.draft.pages.push(page)
      normalizeQuestionOrders(this.draft)
      this.selectedPageCode = page.pageCode
      this.selectedQuestionCode = ''
      this.markDirty()
      return page
    },
    updatePage(pageCode, patch) {
      const page = this.draft?.pages.find(item => item.pageCode === pageCode)
      if (!page) return
      Object.assign(page, patch)
      this.markDirty()
    },
    removePage(pageCode) {
      if (!this.draft || this.draft.pages.length <= 1) return
      const index = this.draft.pages.findIndex(page => page.pageCode === pageCode)
      if (index < 0) return
      this.draft.pages[index].questions.forEach(question => this.removeQuestionBindings(question.questionCode))
      this.draft.pages.splice(index, 1)
      normalizeQuestionOrders(this.draft)
      const selected = this.draft.pages[Math.min(index, this.draft.pages.length - 1)]
      this.selectedPageCode = selected.pageCode
      this.selectedQuestionCode = selected.questions[0]?.questionCode || ''
      this.markDirty()
    },
    movePage(pageCode, offset) {
      if (![1, -1].includes(offset)) return
      const index = this.draft?.pages.findIndex(page => page.pageCode === pageCode) ?? -1
      const targetIndex = index + offset
      if (index < 0 || targetIndex < 0 || targetIndex >= this.draft.pages.length) return
      const [page] = this.draft.pages.splice(index, 1)
      this.draft.pages.splice(targetIndex, 0, page)
      normalizeQuestionOrders(this.draft)
      this.markDirty()
    },
    addQuestion(questionType, pageCode = this.selectedPageCode) {
      const page = this.draft?.pages.find(item => item.pageCode === pageCode)
      const definition = getQuestionTypeDefinition(questionType)
      if (!page || !definition) return null
      const question = definition.createDefault()
      question.sortOrder = page.questions.length + 1
      page.questions.push(question)
      this.selectedPageCode = page.pageCode
      this.selectedQuestionCode = question.questionCode
      normalizeQuestionOrders(this.draft)
      this.markDirty()
      return question
    },
    addSingleChoice() {
      return this.addQuestion('SINGLE_CHOICE')
    },
    updateQuestion(updatedQuestion) {
      const located = locateQuestion(this.draft, updatedQuestion.questionCode)
      if (!located) return
      const definition = getQuestionTypeDefinition(updatedQuestion.questionType)
      located.page.questions.splice(located.index, 1, definition.normalize(updatedQuestion))
      normalizeQuestionOrders(this.draft)
      this.markDirty()
    },
    removeQuestionBindings(questionCode) {
      for (const indicator of this.draft?.indicators || []) {
        indicator.questionCodes = indicator.questionCodes.filter(code => code !== questionCode)
      }
    },
    removeSelectedQuestion() {
      const located = locateQuestion(this.draft, this.selectedQuestionCode)
      if (!located) return
      const removedCode = located.question.questionCode
      located.page.questions.splice(located.index, 1)
      this.removeQuestionBindings(removedCode)
      normalizeQuestionOrders(this.draft)
      this.selectedQuestionCode =
        located.page.questions[Math.min(located.index, located.page.questions.length - 1)]?.questionCode || ''
      this.markDirty()
    },
    duplicateSelectedQuestion() {
      const located = locateQuestion(this.draft, this.selectedQuestionCode)
      if (!located) return
      const duplicated = duplicateQuestion(located.question)
      located.page.questions.splice(located.index + 1, 0, duplicated)
      normalizeQuestionOrders(this.draft)
      this.selectedPageCode = located.page.pageCode
      this.selectedQuestionCode = duplicated.questionCode
      this.markDirty()
      return duplicated
    },
    moveSelectedQuestion(offset) {
      if (![1, -1].includes(offset)) return
      const located = locateQuestion(this.draft, this.selectedQuestionCode)
      if (!located) return
      const targetIndex = located.index + offset
      if (targetIndex < 0 || targetIndex >= located.page.questions.length) return
      const [question] = located.page.questions.splice(located.index, 1)
      located.page.questions.splice(targetIndex, 0, question)
      normalizeQuestionOrders(this.draft)
      this.markDirty()
    },
    moveSelectedQuestionToPage(pageCode) {
      const located = locateQuestion(this.draft, this.selectedQuestionCode)
      const targetPage = this.draft?.pages.find(page => page.pageCode === pageCode)
      if (!located || !targetPage || located.page.pageCode === targetPage.pageCode) return
      const [question] = located.page.questions.splice(located.index, 1)
      targetPage.questions.push(question)
      normalizeQuestionOrders(this.draft)
      this.selectedPageCode = targetPage.pageCode
      this.markDirty()
    },
    addIndicator() {
      const indicator = {
        indicatorId: null,
        indicatorCode: createStableCode('I'),
        indicatorName: `指标${this.draft.indicators.length + 1}`,
        description: '',
        weight: '0.0000',
        sortOrder: this.draft.indicators.length + 1,
        questionCodes: []
      }
      this.draft.indicators.push(indicator)
      normalizeQuestionOrders(this.draft)
      this.markDirty()
      return indicator
    },
    updateIndicator(indicatorCode, patch) {
      const indicator = this.draft?.indicators.find(item => item.indicatorCode === indicatorCode)
      if (!indicator) return
      Object.assign(indicator, patch)
      this.markDirty()
    },
    removeIndicator(indicatorCode) {
      const index = this.draft?.indicators.findIndex(item => item.indicatorCode === indicatorCode) ?? -1
      if (index < 0) return
      this.draft.indicators.splice(index, 1)
      normalizeQuestionOrders(this.draft)
      this.markDirty()
    },
    moveIndicator(indicatorCode, offset) {
      if (![1, -1].includes(offset)) return
      const index = this.draft?.indicators.findIndex(item => item.indicatorCode === indicatorCode) ?? -1
      const targetIndex = index + offset
      if (index < 0 || targetIndex < 0 || targetIndex >= this.draft.indicators.length) return
      const [indicator] = this.draft.indicators.splice(index, 1)
      this.draft.indicators.splice(targetIndex, 0, indicator)
      normalizeQuestionOrders(this.draft)
      this.markDirty()
    },
    setQuestionIndicator(questionCode, indicatorCode) {
      this.removeQuestionBindings(questionCode)
      if (indicatorCode) {
        const indicator = this.draft?.indicators.find(item => item.indicatorCode === indicatorCode)
        if (indicator) indicator.questionCodes.push(questionCode)
      }
      this.markDirty()
    },
    setIndicatorBindings(indicatorCode, questionCodes) {
      const indicator = this.draft?.indicators.find(item => item.indicatorCode === indicatorCode)
      if (!indicator) return
      const uniqueCodes = [...new Set(questionCodes)]
      uniqueCodes.forEach(code => this.removeQuestionBindings(code))
      indicator.questionCodes = uniqueCodes
      this.markDirty()
    },
    validate() {
      return validateQuestionnaireDraft(this.draft)
    },
    async save() {
      if (this.saving || !this.draft) return null
      const errors = this.validate()
      if (errors.length) throw new Error(errors[0])
      this.saving = true
      try {
        const selectedPageCode = this.selectedPageCode
        const selectedQuestionCode = this.selectedQuestionCode
        const response = await saveQuestionnaireDraft(
          this.projectId,
          serializeQuestionnaireDraft(this.draft)
        )
        this.draft = normalizeQuestionnaireDraft(response.data)
        const located = locateQuestion(this.draft, selectedQuestionCode)
        if (located) {
          this.selectedPageCode = located.page.pageCode
          this.selectedQuestionCode = located.question.questionCode
        } else {
          const page = this.draft.pages.find(item => item.pageCode === selectedPageCode) || this.draft.pages[0]
          this.selectedPageCode = page?.pageCode || ''
          this.selectedQuestionCode = page?.questions[0]?.questionCode || ''
        }
        this.dirty = false
        this.lastSavedAt = new Date()
        return this.draft
      } finally {
        this.saving = false
      }
    },
    reset() {
      this.$reset()
    }
  }
})
