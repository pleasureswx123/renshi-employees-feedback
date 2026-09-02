import { defineStore } from 'pinia'

import {
  getPublicationConfig,
  listParticipantOptions,
  publishProject,
  savePublicationConfig
} from '@/api/feedback/projects'
import {
  createCustomRelation,
  normalizePublicationConfig,
  SELF_RELATION_CODE,
  serializePublicationConfig,
  validatePublicationConfig
} from '@/utils/publicationConfig'

function upsertParticipant(items, participant) {
  const index = items.findIndex(item => item.userId === participant.userId)
  if (index < 0) items.push({ ...participant })
  else items.splice(index, 1, { ...items[index], ...participant })
}

export const usePublicationConfigStore = defineStore('publicationConfig', {
  state: () => ({
    projectId: null,
    config: null,
    candidateRows: [],
    candidateTotal: 0,
    candidatePageNum: 1,
    candidatePageSize: 10,
    candidateKeyword: '',
    loading: false,
    candidatesLoading: false,
    saving: false,
    publishing: false,
    dirty: false,
    lastSavedAt: null
  }),
  getters: {
    selectedTargetIds(state) {
      return new Set((state.config?.targets || []).map(item => item.userId))
    },
    participantDirectory(state) {
      const directory = new Map()
      for (const item of state.config?.configuredParticipants || []) directory.set(item.userId, item)
      for (const item of state.candidateRows) directory.set(item.userId, item)
      for (const item of state.config?.targets || []) directory.set(item.userId, item)
      return directory
    },
    editable(state) {
      return Boolean(state.config?.editable)
    }
  },
  actions: {
    async load(projectId) {
      if (this.loading) return
      this.loading = true
      try {
        const response = await getPublicationConfig(projectId)
        this.projectId = Number(projectId)
        this.config = normalizePublicationConfig(response.data)
        this.dirty = false
        this.lastSavedAt = null
      } finally {
        this.loading = false
      }
    },
    async loadCandidates({ pageNum = 1, keyword = this.candidateKeyword } = {}) {
      if (this.candidatesLoading || !this.projectId) return
      this.candidatesLoading = true
      this.candidatePageNum = pageNum
      this.candidateKeyword = keyword
      try {
        const response = await listParticipantOptions(this.projectId, {
          pageNum,
          pageSize: this.candidatePageSize,
          keyword: keyword || undefined
        })
        this.candidateRows = response.rows || []
        this.candidateTotal = Number(response.total || 0)
        for (const item of this.candidateRows) upsertParticipant(this.config.configuredParticipants, item)
      } finally {
        this.candidatesLoading = false
      }
    },
    markDirty() {
      if (this.editable) this.dirty = true
    },
    addTarget(participant) {
      if (!this.editable || this.selectedTargetIds.has(participant.userId)) return
      this.config.targets.push({
        ...participant,
        targetId: null,
        onlySelfEvaluation: true
      })
      upsertParticipant(this.config.configuredParticipants, participant)
      this.markDirty()
    },
    removeTarget(userId) {
      if (!this.editable) return
      this.config.targets = this.config.targets.filter(item => item.userId !== userId)
      this.config.evaluatorSelections = this.config.evaluatorSelections.filter(
        item => item.targetUserId !== userId
      )
      this.markDirty()
    },
    updateRelation(relationCode, patch) {
      if (!this.editable) return
      const relation = this.config.relations.find(item => item.relationCode === relationCode)
      if (!relation || relation.relationCode === SELF_RELATION_CODE && patch.isEnabled === false) return
      Object.assign(relation, patch)
      if (!relation.isEnabled) {
        relation.participatesInScore = false
        relation.weight = '0.0000'
        this.config.evaluatorSelections = this.config.evaluatorSelections.filter(
          item => item.relationCode !== relationCode
        )
      } else if (!relation.participatesInScore) {
        relation.weight = '0.0000'
      }
      this.markDirty()
    },
    addCustomRelation() {
      if (!this.editable || this.config.relations.length >= 100) return
      this.config.relations.push(createCustomRelation(this.config.relations.length + 1))
      this.markDirty()
    },
    removeRelation(relationCode) {
      if (!this.editable) return
      const relation = this.config.relations.find(item => item.relationCode === relationCode)
      if (!relation || relation.fixed) return
      this.config.relations = this.config.relations.filter(item => item.relationCode !== relationCode)
      this.config.evaluatorSelections = this.config.evaluatorSelections.filter(
        item => item.relationCode !== relationCode
      )
      this.config.relations.forEach((item, index) => { item.sortOrder = index + 1 })
      this.markDirty()
    },
    moveRelation(relationCode, offset) {
      if (!this.editable || ![-1, 1].includes(offset)) return
      const index = this.config.relations.findIndex(item => item.relationCode === relationCode)
      const targetIndex = index + offset
      if (index < 0 || targetIndex < 0 || targetIndex >= this.config.relations.length) return
      const [relation] = this.config.relations.splice(index, 1)
      this.config.relations.splice(targetIndex, 0, relation)
      this.config.relations.forEach((item, order) => { item.sortOrder = order + 1 })
      this.markDirty()
    },
    setEvaluatorIds(targetUserId, relationCode, evaluatorUserIds) {
      if (!this.editable || relationCode === SELF_RELATION_CODE) return
      const filteredIds = [...new Set(evaluatorUserIds)].filter(userId => userId !== targetUserId)
      const index = this.config.evaluatorSelections.findIndex(
        item => item.targetUserId === targetUserId && item.relationCode === relationCode
      )
      if (!filteredIds.length && index >= 0) this.config.evaluatorSelections.splice(index, 1)
      else if (index >= 0) this.config.evaluatorSelections[index].evaluatorUserIds = filteredIds
      else if (filteredIds.length) {
        this.config.evaluatorSelections.push({
          targetUserId,
          relationCode,
          evaluatorUserIds: filteredIds,
          systemManaged: false
        })
      }
      this.markDirty()
    },
    evaluatorIds(targetUserId, relationCode) {
      return this.config?.evaluatorSelections.find(
        item => item.targetUserId === targetUserId && item.relationCode === relationCode
      )?.evaluatorUserIds || []
    },
    validate() {
      return validatePublicationConfig(this.config)
    },
    async save() {
      if (this.saving || !this.config || !this.editable) return null
      const errors = this.validate()
      if (errors.length) throw new Error(errors[0])
      this.saving = true
      try {
        const response = await savePublicationConfig(
          this.projectId,
          serializePublicationConfig(this.config)
        )
        this.config = normalizePublicationConfig(response.data)
        this.dirty = false
        this.lastSavedAt = new Date()
        return this.config
      } finally {
        this.saving = false
      }
    },
    async publish() {
      if (this.publishing || !this.config || !this.editable) return null
      if (this.dirty) throw new Error('请先保存当前修改，再发布项目')
      if (!this.config.isPublishReady) throw new Error('发布前检查尚未通过')
      this.publishing = true
      try {
        const response = await publishProject(this.projectId, {
          projectLockVersion: this.config.projectLockVersion,
          versionId: this.config.versionId,
          versionLockVersion: this.config.versionLockVersion
        })
        await this.load(this.projectId)
        return response.data
      } catch (error) {
        if (error.data?.validationIssues?.length) {
          this.config.validationIssues = error.data.validationIssues
          this.config.isPublishReady = false
        }
        throw error
      } finally {
        this.publishing = false
      }
    },
    reset() {
      this.$reset()
    }
  }
})
