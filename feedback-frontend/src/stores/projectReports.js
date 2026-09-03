import { defineStore } from 'pinia'

import { generateReports, getPersonalReport, getSubmittedAnswer, getTeamReport, listReportProjects, listSubmittedAnswers } from '@/api/feedback/reports'

let sequence = 0
const channels = ['projects', 'team', 'person', 'answers', 'answer', 'generate']

export const useProjectReportsStore = defineStore('projectReports', {
  state: () => ({
    projectId: null,
    projects: null,
    team: null,
    person: null,
    answers: null,
    answer: null,
    loading: {},
    epochs: {},
    errors: {}
  }),
  actions: {
    selectProject(id) {
      if (this.projectId !== Number(id)) {
        this.reset()
        this.projectId = Number(id)
      }
    },
    clear(channel) {
      this.epochs[channel] = ++sequence
      this[channel] = null
      this.loading[channel] = false
      this.errors[channel] = ''
    },
    async read(channel, operation, { envelope = false } = {}) {
      this.clear(channel)
      const epoch = this.epochs[channel]
      this.loading[channel] = true
      try {
        const response = await operation()
        if (epoch !== this.epochs[channel]) return null
        this[channel] = envelope ? response : response.data
        return this[channel]
      } catch (error) {
        if (epoch !== this.epochs[channel]) return null
        if ([401, 403, 404].includes(Number(error.status))) {
          this.reset()
        }
        this.errors[channel] = error.message || '加载失败，请重试'
        return null
      } finally {
        if (epoch === this.epochs[channel]) this.loading[channel] = false
      }
    },
    loadProjects(params) {
      return this.read('projects', () => listReportProjects(params), { envelope: true })
    },
    loadTeam(id, params = {}) {
      this.selectProject(id)
      this.clear('person')
      return this.read('team', () => getTeamReport(id, params))
    },
    loadPerson(targetId) {
      return this.read('person', () => getPersonalReport(this.projectId, targetId))
    },
    loadAnswers(id, params = {}) {
      this.selectProject(id)
      this.clear('answer')
      return this.read('answers', () => listSubmittedAnswers(id, params), { envelope: true })
    },
    loadAnswer(assignmentId) {
      return this.read('answer', () => getSubmittedAnswer(this.projectId, assignmentId))
    },
    async generate() {
      if (!this.projectId || this.loading.generate) return null
      const id = this.projectId
      const epoch = ++sequence
      this.epochs.generate = epoch
      this.loading.generate = true
      this.errors.generate = ''
      try {
        const response = await generateReports(id)
        if (epoch !== this.epochs.generate) return null
        await this.loadTeam(id)
        return epoch === this.epochs.generate ? response.data : null
      } catch (error) {
        if (epoch !== this.epochs.generate) return null
        if ([401, 403, 404].includes(Number(error.status))) this.reset()
        this.errors.generate = error.message || '报告生成失败，请重试'
        return null
      } finally {
        if (epoch === this.epochs.generate) this.loading.generate = false
      }
    },
    reset() {
      this.$reset()
      channels.forEach(channel => { this.epochs[channel] = ++sequence })
    }
  }
})
