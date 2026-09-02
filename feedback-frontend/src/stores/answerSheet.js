import { defineStore } from 'pinia'

import { getMyHistory, getMyTask, saveMyDraft, submitMyAnswer } from '@/api/feedback/tasks'
import { allQuestions, hasAnswer, restoreAnswers, serializeAnswers, validateAnswerSheet } from '@/utils/answerSheet'

export const useAnswerSheetStore = defineStore('answerSheet', {
  state: () => ({
    contextEpoch: 0,
    assignmentId: null,
    history: false,
    detail: null,
    answers: {},
    pageIndex: 0,
    dirty: false,
    loading: false,
    saving: false,
    submitting: false,
    error: '',
    issues: [],
    conflict: false,
    closed: false,
    pendingSubmission: null
  }),
  getters: {
    busy: state => state.loading || state.saving || state.submitting,
    editable: state => Boolean(state.detail?.editable && !state.history && !state.closed),
    questions: state => allQuestions(state.detail?.questionnaire),
    answeredCount() {
      return this.questions.filter(({ question }) => hasAnswer(question, this.answers[question.questionCode])).length
    }
  },
  actions: {
    reset() {
      const nextEpoch = this.contextEpoch + 1
      this.$reset()
      this.contextEpoch = nextEpoch
    },
    hydrate(detail) {
      this.detail = detail
      this.answers = restoreAnswers(detail)
      this.pageIndex = Math.max(0, detail.questionnaire.pages.findIndex(page => page.pageId === detail.lastPageId))
      this.dirty = false
      this.issues = []
      this.error = ''
      this.conflict = false
    },
    async load(assignmentId, { history = false } = {}) {
      this.reset()
      const epoch = this.contextEpoch
      this.assignmentId = Number(assignmentId)
      this.history = history
      this.loading = true
      try {
        const response = await (history ? getMyHistory : getMyTask)(this.assignmentId)
        if (epoch !== this.contextEpoch) return null
        this.hydrate(response.data)
        return response.data
      } catch (error) {
        if (epoch === this.contextEpoch) this.recordError(error)
        return null
      } finally {
        if (epoch === this.contextEpoch) this.loading = false
      }
    },
    setAnswer(questionCode, value) {
      if (!this.editable || this.busy) return
      this.answers[questionCode] = value
      this.dirty = true
      this.pendingSubmission = null
    },
    setPage(pageIndex) {
      if (this.busy || pageIndex < 0 || pageIndex >= (this.detail?.questionnaire.pages.length || 0)) return
      this.pageIndex = pageIndex
      if (this.editable) this.dirty = true
    },
    validate(required = true) {
      this.issues = validateAnswerSheet(this.detail?.questionnaire, this.answers, { required })
      return this.issues.length === 0
    },
    payload() {
      return {
        versionId: this.detail.task.versionId,
        lockVersion: this.detail.lockVersion,
        lastPageId: this.detail.questionnaire.pages[this.pageIndex].pageId,
        answers: serializeAnswers(this.detail.questionnaire, this.answers)
      }
    },
    recordError(error) {
      this.error = error.message || '请求失败，请重试'
      this.issues = error.data?.validationIssues || []
      this.conflict = error.data?.code === 'ANSWER_VERSION_CONFLICT'
      if (error.data?.code === 'PROJECT_CLOSED' || ['SUBMITTED', 'CLOSED_INCOMPLETE'].includes(error.data?.taskStatus)) this.closed = true
    },
    async save() {
      return this.write(false)
    },
    async submit() {
      return this.write(true)
    },
    async write(submitting) {
      if (!this.editable || this.busy || this.conflict) return null
      if (!this.validate(submitting)) return null
      const epoch = this.contextEpoch
      const assignmentId = this.assignmentId
      const payload = this.payload()
      if (submitting) {
        this.pendingSubmission ||= { ...payload, submissionId: crypto.randomUUID() }
      }
      this[submitting ? 'submitting' : 'saving'] = true
      try {
        const response = await (submitting ? submitMyAnswer : saveMyDraft)(
          assignmentId, submitting ? this.pendingSubmission : payload
        )
        if (epoch !== this.contextEpoch) return null
        this.hydrate(response.data)
        this.pendingSubmission = null
        return response.data
      } catch (error) {
        if (epoch === this.contextEpoch) this.recordError(error)
        return null
      } finally {
        if (epoch === this.contextEpoch) {
          this.saving = false
          this.submitting = false
        }
      }
    }
  }
})
