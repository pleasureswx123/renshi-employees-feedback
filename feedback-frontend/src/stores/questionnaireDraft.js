import { defineStore } from 'pinia'

import { getQuestionnaireDraft, saveQuestionnaireDraft } from '@/api/feedback/projects'
import {
  createStableCode,
  normalizeQuestionOrders,
  validateSingleChoiceDraft
} from '@/utils/questionnaireDraft'

function defaultOption(label, score, sortOrder) {
  return {
    optionId: null,
    optionCode: createStableCode('O'),
    optionLabel: label,
    score,
    requiresReason: false,
    sortOrder
  }
}

function duplicateQuestion(question) {
  return {
    ...question,
    questionId: null,
    questionCode: createStableCode('Q'),
    title: `${question.title.slice(0, 1996)}（副本）`,
    options: question.options.map(option => ({
      ...option,
      optionId: null,
      optionCode: createStableCode('O')
    }))
  }
}

export const useQuestionnaireDraftStore = defineStore('questionnaireDraft', {
  state: () => ({
    projectId: null,
    draft: null,
    selectedQuestionCode: '',
    loading: false,
    saving: false,
    dirty: false,
    lastSavedAt: null
  }),
  getters: {
    selectedQuestion(state) {
      return (
        state.draft?.pages
          ?.flatMap(page => page.questions)
          .find(question => question.questionCode === state.selectedQuestionCode) || null
      )
    }
  },
  actions: {
    async load(projectId) {
      if (this.loading) return
      this.loading = true
      try {
        const response = await getQuestionnaireDraft(projectId)
        this.projectId = Number(projectId)
        this.draft = normalizeQuestionOrders(response.data)
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
    selectQuestion(questionCode) {
      this.selectedQuestionCode = questionCode
    },
    addSingleChoice() {
      const page = this.draft?.pages?.[0]
      if (!page) return
      const question = {
        questionId: null,
        questionCode: createStableCode('Q'),
        questionType: 'SINGLE_CHOICE',
        title: '新的单选题',
        description: '',
        isRequired: false,
        isScored: true,
        sortOrder: page.questions.length + 1,
        options: [defaultOption('选项1', 1, 1), defaultOption('选项2', 0, 2)]
      }
      page.questions.push(question)
      this.selectedQuestionCode = question.questionCode
      this.markDirty()
    },
    updateQuestion(updatedQuestion) {
      const page = this.draft?.pages?.find(item =>
        item.questions.some(question => question.questionCode === updatedQuestion.questionCode)
      )
      if (!page) return
      const index = page.questions.findIndex(
        question => question.questionCode === updatedQuestion.questionCode
      )
      page.questions.splice(index, 1, updatedQuestion)
      normalizeQuestionOrders(this.draft)
      this.markDirty()
    },
    removeSelectedQuestion() {
      const page = this.draft?.pages?.find(item =>
        item.questions.some(question => question.questionCode === this.selectedQuestionCode)
      )
      if (!page) return
      const index = page.questions.findIndex(
        question => question.questionCode === this.selectedQuestionCode
      )
      page.questions.splice(index, 1)
      normalizeQuestionOrders(this.draft)
      this.selectedQuestionCode = page.questions[Math.min(index, page.questions.length - 1)]?.questionCode || ''
      this.markDirty()
    },
    duplicateSelectedQuestion() {
      const page = this.draft?.pages?.find(item =>
        item.questions.some(question => question.questionCode === this.selectedQuestionCode)
      )
      if (!page) return
      const index = page.questions.findIndex(
        question => question.questionCode === this.selectedQuestionCode
      )
      const duplicated = duplicateQuestion(page.questions[index])
      page.questions.splice(index + 1, 0, duplicated)
      normalizeQuestionOrders(this.draft)
      this.selectedQuestionCode = duplicated.questionCode
      this.markDirty()
    },
    moveSelectedQuestion(offset) {
      if (![1, -1].includes(offset)) return
      const page = this.draft?.pages?.find(item =>
        item.questions.some(question => question.questionCode === this.selectedQuestionCode)
      )
      if (!page) return
      const index = page.questions.findIndex(
        question => question.questionCode === this.selectedQuestionCode
      )
      const targetIndex = index + offset
      if (targetIndex < 0 || targetIndex >= page.questions.length) return
      const [question] = page.questions.splice(index, 1)
      page.questions.splice(targetIndex, 0, question)
      normalizeQuestionOrders(this.draft)
      this.markDirty()
    },
    validate() {
      return validateSingleChoiceDraft(this.draft)
    },
    async save() {
      if (this.saving || !this.draft) return null
      const errors = this.validate()
      if (errors.length) throw new Error(errors[0])
      this.saving = true
      try {
        normalizeQuestionOrders(this.draft)
        const response = await saveQuestionnaireDraft(this.projectId, {
          versionId: this.draft.versionId,
          lockVersion: this.draft.lockVersion,
          title: this.draft.title,
          description: this.draft.description || null,
          settings: this.draft.settings || {},
          pages: this.draft.pages
        })
        const selectedIndex = this.draft.pages[0]?.questions.findIndex(
          question => question.questionCode === this.selectedQuestionCode
        )
        this.draft = normalizeQuestionOrders(response.data)
        this.selectedQuestionCode = this.draft.pages[0]?.questions[selectedIndex]?.questionCode || ''
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
