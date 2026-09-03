import { defineStore } from 'pinia'

import {
  completeProject,
  getCompletionPrecheck,
  getProject,
  getProjectProgress
} from '@/api/feedback/projects'

const summaryKeys = [
  'totalCount',
  'submittedCount',
  'draftCount',
  'pendingCount',
  'closedIncompleteCount'
]
let requestSequence = 0

const defaultFilters = () => ({
  evaluatorUserId: null,
  targetUserId: null,
  relationId: null,
  status: '',
  evaluatorKeyword: '',
  targetKeyword: '',
  pageNum: 1,
  pageSize: 20
})

function requestParams(filters) {
  return Object.fromEntries(
    Object.entries(filters)
      .map(([key, value]) => [key, typeof value === 'string' ? value.trim() : value])
      .filter(([, value]) => value !== '' && value !== null && value !== undefined)
  )
}

function isCompletionResultUnknown(error) {
  const status = Number(error?.status || 0)
  return error?.requestSent === true && (
    ['TIMEOUT', 'NETWORK', 'HTTP_SERVER', 'RESPONSE_PROCESSING'].includes(error?.kind) || status >= 500
  )
}

function clearVisibleProgress(store) {
  store.project = null
  store.summary = null
  store.dataScopeComplete = false
  store.scopeMessage = null
  store.relations = []
  store.rows = []
  store.total = 0
  store.precheck = null
  store.projectDetail = null
  store.detailsStale = false
}

export const useProjectProgressStore = defineStore('projectProgress', {
  state: () => ({
    projectId: null,
    project: null,
    summary: null,
    dataScopeComplete: true,
    scopeMessage: null,
    relations: [],
    rows: [],
    total: 0,
    detailsStale: false,
    filters: defaultFilters(),
    loading: false,
    prechecking: false,
    precheck: null,
    completing: false,
    completionResult: null,
    completionIssue: null,
    completionResultUnknown: false,
    verifyingCompletion: false,
    projectDetail: null,
    epoch: 0,
    precheckEpoch: 0,
    completionEpoch: 0,
    completionVerificationEpoch: 0
  }),
  getters: {
    expectedSummary(state) {
      if (!state.precheck?.summary) return null
      return Object.fromEntries(summaryKeys.map(key => [key, state.precheck.summary[key]]))
    }
  },
  actions: {
    async load(projectId = this.projectId) {
      if (!projectId) return null
      if (this.projectId !== null && Number(projectId) !== this.projectId) {
        this.precheckEpoch = ++requestSequence
        this.completionEpoch = ++requestSequence
        this.prechecking = false
        this.completing = false
        this.verifyingCompletion = false
        this.precheck = null
        this.completionResult = null
        this.completionIssue = null
        this.completionResultUnknown = false
        this.detailsStale = false
        this.projectDetail = null
        this.completionVerificationEpoch = ++requestSequence
      }
      const epoch = ++requestSequence
      this.epoch = epoch
      this.loading = true
      try {
        const response = await getProjectProgress(projectId, requestParams(this.filters))
        if (epoch !== this.epoch) return null
        const data = response.data
        this.projectId = Number(projectId)
        this.project = {
          projectId: data.projectId,
          projectName: data.projectName,
          projectStatus: data.projectStatus,
          projectLockVersion: data.projectLockVersion
        }
        this.summary = data.summary
        this.dataScopeComplete = data.dataScopeComplete
        this.scopeMessage = data.scopeMessage
        this.relations = data.filterOptions?.relations || []
        this.rows = data.rows || []
        this.total = Number(data.total || 0)
        this.detailsStale = false
        this.filters.pageNum = data.pageNum
        this.filters.pageSize = data.pageSize
        return data
      } catch (error) {
        if (epoch !== this.epoch) return null
        if ([403, 404].includes(Number(error?.status))) {
          clearVisibleProgress(this)
        }
        throw error
      } finally {
        if (epoch === this.epoch) this.loading = false
      }
    },
    async search() {
      this.filters.pageNum = 1
      return this.load()
    },
    async changePage(pageNum) {
      this.filters.pageNum = pageNum
      return this.load()
    },
    async precheckCompletion() {
      if (!this.projectId || this.prechecking || this.completionResultUnknown) return null
      const projectId = this.projectId
      const precheckEpoch = ++requestSequence
      this.precheckEpoch = precheckEpoch
      this.prechecking = true
      try {
        const response = await getCompletionPrecheck(projectId)
        if (precheckEpoch !== this.precheckEpoch) return null
        const precheck = response.data
        this.precheck = precheck
        this.project = {
          projectId: precheck.projectId,
          projectName: precheck.projectName,
          projectStatus: precheck.projectStatus,
          projectLockVersion: precheck.projectLockVersion
        }
        this.summary = precheck.summary
        this.dataScopeComplete = precheck.dataScopeComplete
        this.scopeMessage = precheck.dataScopeComplete
          ? null
          : precheck.scopeMessage ?? '当前数据范围仅覆盖部分被评价人'
        if (!precheck.dataScopeComplete) {
          this.relations = []
          this.rows = []
          this.total = 0
          this.detailsStale = true
        }
        if (precheck.projectStatus === 'COMPLETED') {
          try {
            await this.load(projectId)
          } catch {
            // 预检已经返回持久化完成结果，进度刷新失败不能把页面退回可操作状态。
          }
          if (precheckEpoch !== this.precheckEpoch) return null
          this.precheck = precheck
          this.project = {
            projectId: precheck.projectId,
            projectName: precheck.projectName,
            projectStatus: precheck.projectStatus,
            projectLockVersion: precheck.projectLockVersion
          }
          this.summary = precheck.summary
          this.dataScopeComplete = precheck.dataScopeComplete
          this.scopeMessage = precheck.scopeMessage ?? null
        }
        return this.precheck
      } catch (error) {
        if (precheckEpoch !== this.precheckEpoch) return null
        if ([403, 404].includes(Number(error?.status))) clearVisibleProgress(this)
        this.completionIssue = {
          code: error?.data?.code || error?.kind || 'COMPLETION_PRECHECK_FAILED',
          message: error?.message || '完成预检失败，请稍后重试。'
        }
        throw error
      } finally {
        if (precheckEpoch === this.precheckEpoch) this.prechecking = false
      }
    },
    async complete(completionReason, { refreshProjectDetail = false } = {}) {
      if (!this.projectId || !this.precheck || this.completing || this.completionResultUnknown) return null
      const projectId = this.projectId
      const completionEpoch = ++requestSequence
      this.completionEpoch = completionEpoch
      this.completing = true
      this.completionIssue = null
      try {
        const response = await completeProject(projectId, {
          projectLockVersion: this.precheck.projectLockVersion,
          completionReason: completionReason.trim(),
          expectedSummary: this.expectedSummary
        })
        if (completionEpoch !== this.completionEpoch) return null
        this.completionResult = response.data
        this.completionResultUnknown = false
        this.precheck = null
        this.project = {
          ...this.project,
          projectId: response.data.projectId,
          projectStatus: response.data.projectStatus,
          projectLockVersion: response.data.projectLockVersion
        }
        this.summary = response.data.summary
        const [detail, refreshedProgress] = await Promise.allSettled([
          refreshProjectDetail ? getProject(projectId) : Promise.resolve(null),
          this.load(projectId)
        ])
        if (completionEpoch !== this.completionEpoch) return null
        if (refreshProjectDetail && detail.status === 'fulfilled' && this.projectId === projectId) {
          this.projectDetail = detail.value.data
        }
        if ((refreshProjectDetail && detail.status === 'rejected') || refreshedProgress.status === 'rejected') {
          this.completionIssue = {
            code: 'COMPLETION_REFRESH_FAILED',
            message: '项目已完成，但部分最新信息刷新失败；当前页面已锁定为只读，请稍后手动刷新核对。'
          }
        }
        return response.data
      } catch (error) {
        if (completionEpoch !== this.completionEpoch) return null
        if (error.data?.code === 'COMPLETION_PRECHECK_STALE' && error.data.latestPrecheck) {
          const latest = error.data.latestPrecheck
          this.precheck = null
          this.detailsStale = true
          this.summary = latest.summary
          this.dataScopeComplete = latest.dataScopeComplete
          this.scopeMessage = latest.scopeMessage ?? null
          this.project = {
            projectId: latest.projectId,
            projectName: latest.projectName,
            projectStatus: latest.projectStatus,
            projectLockVersion: latest.projectLockVersion
          }
          this.completionIssue = {
            code: 'COMPLETION_PRECHECK_STALE',
            message: '回收数据已变化，请重新阅读最新预检并再次确认。'
          }
          try {
            await this.load(projectId)
          } catch {
            // 最新预检仍可更新KPI；明细刷新失败时保留过期标记，禁止冒充最新明细。
          }
          if (completionEpoch !== this.completionEpoch) return null
        } else if (error.data?.code === 'PROJECT_COMPLETION_SCOPE_FORBIDDEN') {
          this.precheck = null
          this.summary = null
          this.relations = []
          this.rows = []
          this.total = 0
          this.dataScopeComplete = false
          this.scopeMessage = '当前数据范围仅覆盖部分被评价人'
          this.completionIssue = {
            code: 'PROJECT_COMPLETION_SCOPE_FORBIDDEN',
            message: '当前数据范围不能覆盖全部被评价人，禁止完成整个项目。'
          }
          try {
            await this.load(projectId)
          } catch {
            // 权限范围刷新失败时继续保持清空，禁止回显已经失去权限的旧数据。
          }
          if (completionEpoch !== this.completionEpoch) return null
        } else if (error.status === 409 && ['PROJECT_VERSION_CONFLICT', 'PROJECT_NOT_ACTIVE'].includes(error.data?.code)) {
          this.precheck = null
          this.completionIssue = { code: error.data.code, message: error.message }
        } else if ([403, 404].includes(Number(error.status))) {
          clearVisibleProgress(this)
          this.completionIssue = {
            code: error.data?.code || (Number(error.status) === 404 ? 'NOT_FOUND' : 'FORBIDDEN'),
            message: error.message
          }
        } else if (isCompletionResultUnknown(error)) {
          this.precheck = null
          this.completionResultUnknown = true
          this.completionIssue = {
            code: 'COMPLETION_RESULT_UNKNOWN',
            message: '完成请求可能已经到达服务端，当前结果未知。请先重新核对，系统不会自动重发完成请求。'
          }
        } else {
          this.completionIssue = {
            code: error?.data?.code || error?.kind || 'PROJECT_COMPLETION_FAILED',
            message: error?.message || '完成项目失败，请检查输入后重试。'
          }
        }
        throw error
      } finally {
        if (completionEpoch === this.completionEpoch) this.completing = false
      }
    },
    async recheckCompletionResult() {
      if (!this.projectId || !this.completionResultUnknown || this.verifyingCompletion) return null
      const projectId = this.projectId
      const verificationEpoch = ++requestSequence
      this.completionVerificationEpoch = verificationEpoch
      this.verifyingCompletion = true
      try {
        const progress = await this.load(projectId)
        if (verificationEpoch !== this.completionVerificationEpoch || this.projectId !== projectId) return null
        if (!progress) {
          this.completionResultUnknown = true
          this.completionIssue = {
            code: 'COMPLETION_RESULT_UNKNOWN',
            message: '本次核对没有取得有效的服务端状态，完成操作仍保持锁定，请再次核对。'
          }
          return null
        }
        if (progress?.projectStatus !== 'COMPLETED') {
          this.precheck = null
          this.completionResultUnknown = false
          this.completionIssue = {
            code: 'COMPLETION_RECHECK_ACTIVE',
            message: '服务端仍显示项目进行中；如需再次完成，请重新执行实时预检。'
          }
          return progress
        }
        const response = await getCompletionPrecheck(projectId)
        if (verificationEpoch !== this.completionVerificationEpoch || this.projectId !== projectId) return null
        const precheck = response.data
        this.precheck = precheck
        this.project = {
          projectId: precheck.projectId,
          projectName: precheck.projectName,
          projectStatus: precheck.projectStatus,
          projectLockVersion: precheck.projectLockVersion
        }
        this.summary = precheck.summary
        this.dataScopeComplete = precheck.dataScopeComplete
        this.scopeMessage = precheck.scopeMessage ?? null
        this.completionResultUnknown = false
        this.completionIssue = null
        return precheck
      } catch (error) {
        if (verificationEpoch !== this.completionVerificationEpoch) return null
        this.completionResultUnknown = true
        this.completionIssue = {
          code: 'COMPLETION_RESULT_UNKNOWN',
          message: '重新核对失败，完成操作仍处于锁定状态；请稍后再次核对。'
        }
        throw error
      } finally {
        if (verificationEpoch === this.completionVerificationEpoch) this.verifyingCompletion = false
      }
    },
    reset() {
      this.$reset()
      this.epoch = ++requestSequence
      this.precheckEpoch = ++requestSequence
      this.completionEpoch = ++requestSequence
      this.completionVerificationEpoch = ++requestSequence
    }
  }
})
