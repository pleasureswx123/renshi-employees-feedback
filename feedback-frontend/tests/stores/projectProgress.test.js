import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  completeProject: vi.fn(),
  getCompletionPrecheck: vi.fn(),
  getProject: vi.fn(),
  getProjectProgress: vi.fn()
}))
vi.mock('@/api/feedback/projects', () => api)

const { useProjectProgressStore } = await import('@/stores/projectProgress')
const { useAuthStore } = await import('@/stores/auth')

function summary(overrides = {}) {
  return {
    totalCount: 10,
    submittedCount: 6,
    draftCount: 2,
    pendingCount: 2,
    closedIncompleteCount: 0,
    incompleteCount: 4,
    completionRate: '60.00',
    ...overrides
  }
}

function progress(overrides = {}) {
  return {
    projectId: 12,
    projectName: '年度反馈',
    projectStatus: 'ACTIVE',
    projectLockVersion: 3,
    dataScopeComplete: true,
    scopeMessage: null,
    summary: summary(),
    filterOptions: {
      relations: [{ relationId: 8, relationCode: 'PEER', relationName: '同级', sortOrder: 2 }]
    },
    rows: [{ assignmentId: 101, evaluatorName: '张三', targetName: '李四', relationId: 8, relationName: '同级', status: 'DRAFT' }],
    total: 1,
    pageNum: 1,
    pageSize: 20,
    ...overrides
  }
}

function completionPrecheck(overrides = {}) {
  return {
    projectId: 12,
    projectName: '年度反馈',
    projectStatus: 'ACTIVE',
    projectLockVersion: 3,
    dataScopeComplete: true,
    canComplete: true,
    completedBy: null,
    completedTime: null,
    completionReason: null,
    alreadyCompleted: false,
    summary: summary(),
    missingRelations: [],
    impactMessages: ['完成后未提交任务将关闭。'],
    precheckedAt: '2026-09-02T10:05:00',
    ...overrides
  }
}

function deferred() {
  let resolve
  let reject
  const promise = new Promise((done, fail) => { resolve = done; reject = fail })
  return { promise, resolve, reject }
}

describe('项目评价进度Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    Object.values(api).forEach(fn => fn.mockReset())
  })

  it('从服务端加载真实统计、完整范围标识、关系筛选项和分页明细', async () => {
    api.getProjectProgress.mockResolvedValue({ data: progress() })
    const store = useProjectProgressStore()

    await store.load(12)

    expect(api.getProjectProgress).toHaveBeenCalledWith(12, { pageNum: 1, pageSize: 20 })
    expect(store.project.projectName).toBe('年度反馈')
    expect(store.summary.completionRate).toBe('60.00')
    expect(store.dataScopeComplete).toBe(true)
    expect(store.scopeMessage).toBeNull()
    expect(store.relations).toEqual([{ relationId: 8, relationCode: 'PEER', relationName: '同级', sortOrder: 2 }])
    expect(store.rows).toHaveLength(1)
    expect(store.total).toBe(1)
  })

  it('筛选和分页重新请求服务端并忽略项目切换后的迟到响应', async () => {
    api.getProjectProgress.mockResolvedValue({ data: progress() })
    const store = useProjectProgressStore()
    await store.load(12)
    store.filters.evaluatorKeyword = ' 张三 '
    store.filters.targetKeyword = '李四'
    store.filters.relationId = 8
    store.filters.status = 'DRAFT'

    await store.search()
    expect(api.getProjectProgress).toHaveBeenLastCalledWith(12, {
      pageNum: 1,
      pageSize: 20,
      evaluatorKeyword: '张三',
      targetKeyword: '李四',
      relationId: 8,
      status: 'DRAFT'
    })

    api.getProjectProgress.mockResolvedValue({ data: progress({ pageNum: 2 }) })
    await store.changePage(2)
    expect(api.getProjectProgress).toHaveBeenLastCalledWith(12, expect.objectContaining({ pageNum: 2 }))

    const old = deferred()
    api.getProjectProgress.mockReturnValueOnce(old.promise).mockResolvedValue({
      data: progress({ projectId: 13, projectName: '新项目' })
    })
    const oldLoad = store.load(12, { force: true })
    await store.load(13, { force: true })
    old.resolve({ data: progress({ projectName: '迟到旧项目' }) })
    await oldLoad
    expect(store.projectId).toBe(13)
    expect(store.project.projectName).toBe('新项目')
  })

  it('每次完成前实时预检并仅取五个权威计数字段构造完成请求', async () => {
    api.getProjectProgress.mockResolvedValue({ data: progress() })
    const pending = deferred()
    const precheck = completionPrecheck({
      missingRelations: [{ targetUserId: 21, targetName: '李四', relationId: 8, relationName: '同级', assignmentCount: 2, submittedCount: 0 }],
      impactMessages: ['完成后未提交任务将关闭。'],
      precheckedAt: '2026-09-02T10:05:00'
    })
    api.getCompletionPrecheck.mockReturnValue(pending.promise)
    const store = useProjectProgressStore()
    await store.load(12)

    const first = store.precheckCompletion()
    expect(await store.precheckCompletion()).toBeNull()
    pending.resolve({ data: precheck })
    await first

    expect(api.getCompletionPrecheck).toHaveBeenCalledTimes(1)
    expect(store.precheck).toEqual(precheck)
    expect(store.expectedSummary).toEqual({
      totalCount: 10,
      submittedCount: 6,
      draftCount: 2,
      pendingCount: 2,
      closedIncompleteCount: 0
    })
  })

  it('完成时防重入并在成功后刷新项目详情与服务端进度', async () => {
    api.getProjectProgress.mockResolvedValue({ data: progress() })
    api.getCompletionPrecheck.mockResolvedValue({ data: completionPrecheck() })
    const completing = deferred()
    api.completeProject.mockReturnValue(completing.promise)
    api.getProject.mockResolvedValue({ data: { projectId: 12, status: 'COMPLETED', completionReason: '本轮截止' } })
    const store = useProjectProgressStore()
    await store.load(12)
    await store.precheckCompletion()

    const first = store.complete('  本轮截止  ', { refreshProjectDetail: true })
    expect(await store.complete('重复提交')).toBeNull()
    completing.resolve({ data: { projectId: 12, projectStatus: 'COMPLETED', alreadyCompleted: false } })
    api.getProjectProgress.mockResolvedValue({
      data: progress({ projectStatus: 'COMPLETED', summary: summary({ draftCount: 0, pendingCount: 0, closedIncompleteCount: 4 }) })
    })
    await first

    expect(api.completeProject).toHaveBeenCalledTimes(1)
    expect(api.completeProject).toHaveBeenCalledWith(12, {
      projectLockVersion: 3,
      completionReason: '本轮截止',
      expectedSummary: {
        totalCount: 10,
        submittedCount: 6,
        draftCount: 2,
        pendingCount: 2,
        closedIncompleteCount: 0
      }
    })
    expect(api.getProject).toHaveBeenCalledWith(12)
    expect(api.getProjectProgress).toHaveBeenCalledTimes(2)
    expect(store.project.projectStatus).toBe('COMPLETED')
    expect(store.precheck).toBeNull()
    expect(store.projectDetail.completionReason).toBe('本轮截止')
    expect(store.completing).toBe(false)
  })

  it('无project:list权限时完成后只用完成响应和progress刷新且不请求项目详情', async () => {
    api.getProjectProgress
      .mockResolvedValueOnce({ data: progress() })
      .mockResolvedValueOnce({ data: progress({
        projectStatus: 'COMPLETED',
        projectLockVersion: 4,
        summary: summary({ draftCount: 0, pendingCount: 0, closedIncompleteCount: 4 })
      }) })
    api.getCompletionPrecheck.mockResolvedValue({ data: completionPrecheck() })
    api.completeProject.mockResolvedValue({ data: {
      projectId: 12,
      projectStatus: 'COMPLETED',
      projectLockVersion: 4,
      completedBy: 7,
      completedTime: '2026-09-02T10:06:00',
      completionReason: '本轮截止',
      alreadyCompleted: false,
      summary: summary({ draftCount: 0, pendingCount: 0, closedIncompleteCount: 4 })
    } })
    const store = useProjectProgressStore()
    await store.load(12)
    await store.precheckCompletion()

    await store.complete('本轮截止')

    expect(api.getProject).not.toHaveBeenCalled()
    expect(api.getProjectProgress).toHaveBeenCalledTimes(2)
    expect(store.project.projectStatus).toBe('COMPLETED')
    expect(store.completionIssue).toBeNull()
  })

  it('409预检过期时关闭旧确认、标记明细过期并按当前筛选刷新', async () => {
    const refreshedRows = [{ assignmentId: 102, evaluatorName: '王五', targetName: '赵六', relationId: 8, relationName: '同级', status: 'DRAFT' }]
    api.getProjectProgress
      .mockResolvedValueOnce({ data: progress() })
      .mockResolvedValueOnce({ data: progress({
        projectLockVersion: 4,
        summary: summary({ submittedCount: 7, draftCount: 1 }),
        rows: refreshedRows
      }) })
    api.getCompletionPrecheck.mockResolvedValue({ data: completionPrecheck() })
    const latestPrecheck = completionPrecheck({
      projectLockVersion: 4,
      summary: summary({ submittedCount: 7, draftCount: 1 })
    })
    api.completeProject.mockRejectedValue(Object.assign(new Error('统计已变化'), {
      status: 409,
      data: { code: 'COMPLETION_PRECHECK_STALE', latestPrecheck }
    }))
    const store = useProjectProgressStore()
    await store.load(12)
    store.filters.status = 'DRAFT'
    await store.precheckCompletion()

    await expect(store.complete('本轮截止')).rejects.toThrow('统计已变化')

    expect(store.precheck).toBeNull()
    expect(store.summary.submittedCount).toBe(7)
    expect(store.project.projectLockVersion).toBe(4)
    expect(api.getProjectProgress).toHaveBeenCalledTimes(2)
    expect(api.getProjectProgress).toHaveBeenLastCalledWith(12, expect.objectContaining({ status: 'DRAFT' }))
    expect(store.rows).toEqual(refreshedRows)
    expect(store.detailsStale).toBe(false)
    expect(store.completionIssue).toEqual({
      code: 'COMPLETION_PRECHECK_STALE',
      message: '回收数据已变化，请重新阅读最新预检并再次确认。'
    })
    expect(api.completeProject).toHaveBeenCalledTimes(1)
  })

  it('409预检过期后的明细刷新失败时保持过期标记且不自动重发完成', async () => {
    const latestPrecheck = completionPrecheck({
      projectLockVersion: 4,
      summary: summary({ submittedCount: 7, draftCount: 1 })
    })
    api.getProjectProgress
      .mockResolvedValueOnce({ data: progress() })
      .mockRejectedValueOnce(new Error('明细刷新失败'))
    api.getCompletionPrecheck.mockResolvedValue({ data: completionPrecheck() })
    api.completeProject.mockRejectedValue(Object.assign(new Error('统计已变化'), {
      status: 409,
      data: { code: 'COMPLETION_PRECHECK_STALE', latestPrecheck }
    }))
    const store = useProjectProgressStore()
    await store.load(12)
    await store.precheckCompletion()

    await expect(store.complete('本轮截止')).rejects.toThrow('统计已变化')

    expect(store.precheck).toBeNull()
    expect(store.detailsStale).toBe(true)
    expect(api.getProjectProgress).toHaveBeenCalledTimes(2)
    expect(api.completeProject).toHaveBeenCalledTimes(1)
  })

  it('403局部范围拒绝时关闭确认并保留明确问题码', async () => {
    api.getProjectProgress
      .mockResolvedValueOnce({ data: progress() })
      .mockRejectedValueOnce(new Error('范围刷新失败'))
    api.getCompletionPrecheck.mockResolvedValue({ data: completionPrecheck() })
    api.completeProject.mockRejectedValue(Object.assign(new Error('数据范围不完整'), {
      status: 403,
      data: { code: 'PROJECT_COMPLETION_SCOPE_FORBIDDEN' }
    }))
    const store = useProjectProgressStore()
    await store.load(12)
    await store.precheckCompletion()

    await expect(store.complete('本轮截止')).rejects.toThrow('数据范围不完整')

    expect(store.precheck).toBeNull()
    expect(store.dataScopeComplete).toBe(false)
    expect(store.scopeMessage).toBe('当前数据范围仅覆盖部分被评价人')
    expect(store.completionIssue.code).toBe('PROJECT_COMPLETION_SCOPE_FORBIDDEN')
    expect(api.getProjectProgress).toHaveBeenCalledTimes(2)
    expect(store.rows).toEqual([])
    expect(store.relations).toEqual([])
    expect(store.total).toBe(0)
    expect(store.summary).toBeNull()
  })

  it.each([
    ['TIMEOUT', 0, '系统接口请求超时'],
    ['NETWORK', 0, '网络连接中断'],
    ['HTTP_SERVER', 500, '服务端处理异常'],
    ['RESPONSE_PROCESSING', 200, '响应解密失败']
  ])('%s且请求已发出时锁定完成操作，人工核对ACTIVE后才允许重新预检', async (kind, status, message) => {
    api.getProjectProgress.mockResolvedValue({ data: progress() })
    api.getCompletionPrecheck.mockResolvedValue({ data: completionPrecheck() })
    api.completeProject.mockRejectedValue(Object.assign(new Error(message), {
      kind,
      status,
      requestSent: true
    }))
    const store = useProjectProgressStore()
    await store.load(12)
    await store.precheckCompletion()

    await expect(store.complete('本轮截止')).rejects.toThrow(message)

    expect(store.precheck).toBeNull()
    expect(store.completionResultUnknown).toBe(true)
    expect(store.completionIssue.code).toBe('COMPLETION_RESULT_UNKNOWN')
    expect(api.getProjectProgress).toHaveBeenCalledTimes(1)
    expect(await store.complete('禁止自动重发')).toBeNull()
    expect(api.completeProject).toHaveBeenCalledTimes(1)

    await store.recheckCompletionResult()

    expect(api.getProjectProgress).toHaveBeenCalledTimes(2)
    expect(store.completionResultUnknown).toBe(false)
    expect(store.completionIssue.code).toBe('COMPLETION_RECHECK_ACTIVE')
    await store.precheckCompletion()
    expect(api.getCompletionPrecheck).toHaveBeenCalledTimes(2)
    expect(api.completeProject).toHaveBeenCalledTimes(1)
  })

  it.each(['DUPLICATE_MUTATION', 'REQUEST_SETUP'])('%s等本地未发出错误不会误判完成结果未知', async kind => {
    api.getProjectProgress.mockResolvedValue({ data: progress() })
    api.getCompletionPrecheck.mockResolvedValue({ data: completionPrecheck() })
    api.completeProject.mockRejectedValue(Object.assign(new Error('请求发送前失败'), {
      kind,
      status: 0,
      requestSent: false
    }))
    const store = useProjectProgressStore()
    await store.load(12)
    await store.precheckCompletion()

    await expect(store.complete('本轮截止')).rejects.toThrow('请求发送前失败')

    expect(store.completionResultUnknown).toBe(false)
    expect(store.precheck).not.toBeNull()
    expect(api.getProjectProgress).toHaveBeenCalledTimes(1)
  })

  it('人工核对确认COMPLETED后解除未知锁定并保存只读完成结果', async () => {
    const completed = completionPrecheck({
      projectStatus: 'COMPLETED',
      projectLockVersion: 4,
      canComplete: false,
      completedBy: 7,
      completedTime: '2026-09-02T10:06:00',
      completionReason: '本轮评价截止',
      alreadyCompleted: true,
      summary: summary({ draftCount: 0, pendingCount: 0, closedIncompleteCount: 4 })
    })
    api.getProjectProgress
      .mockResolvedValueOnce({ data: progress() })
      .mockResolvedValueOnce({ data: progress({ projectStatus: 'COMPLETED', projectLockVersion: 4, summary: completed.summary }) })
    api.getCompletionPrecheck
      .mockResolvedValueOnce({ data: completionPrecheck() })
      .mockResolvedValueOnce({ data: completed })
    api.completeProject.mockRejectedValue(Object.assign(new Error('网关超时'), {
      kind: 'HTTP_SERVER',
      status: 504,
      requestSent: true
    }))
    const store = useProjectProgressStore()
    await store.load(12)
    await store.precheckCompletion()
    await expect(store.complete('本轮截止')).rejects.toThrow('网关超时')

    const result = await store.recheckCompletionResult()

    expect(result.projectStatus).toBe('COMPLETED')
    expect(store.completionResultUnknown).toBe(false)
    expect(store.precheck.completedBy).toBe(7)
    expect(store.project.projectStatus).toBe('COMPLETED')
  })

  it.each([
    ['PROJECT_VERSION_CONFLICT', '项目版本已变化，请重新执行完成预检。'],
    ['PROJECT_NOT_ACTIVE', '项目当前不是进行阶段，不能执行完成操作。']
  ])('409 %s关闭旧确认且不自动重试', async (code, message) => {
    api.getProjectProgress.mockResolvedValue({ data: progress() })
    api.getCompletionPrecheck.mockResolvedValue({ data: completionPrecheck() })
    api.completeProject.mockRejectedValue(Object.assign(new Error(message), { status: 409, data: { code } }))
    const store = useProjectProgressStore()
    await store.load(12)
    await store.precheckCompletion()

    await expect(store.complete('本轮截止')).rejects.toThrow(message)

    expect(store.precheck).toBeNull()
    expect(store.completionIssue).toEqual({ code, message })
    expect(api.completeProject).toHaveBeenCalledTimes(1)
  })

  it('退出登录清空Store且迟到响应不能重新写入', async () => {
    const pending = deferred()
    api.getProjectProgress.mockReturnValue(pending.promise)
    const store = useProjectProgressStore()
    const loading = store.load(12)
    useAuthStore().clearSession()
    pending.resolve({ data: progress() })
    await loading

    expect(store.projectId).toBeNull()
    expect(store.rows).toEqual([])
    expect(store.precheck).toBeNull()
  })

  it('退出后新会话发起请求时旧会话响应仍不能覆盖', async () => {
    const old = deferred()
    const current = deferred()
    api.getProjectProgress.mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise)
    const store = useProjectProgressStore()
    const oldLoad = store.load(12)
    useAuthStore().clearSession()
    const currentLoad = store.load(13)
    current.resolve({ data: progress({ projectId: 13, projectName: '当前会话项目' }) })
    await currentLoad
    old.resolve({ data: progress({ projectName: '旧会话项目' }) })
    await oldLoad
    expect(store.projectId).toBe(13)
    expect(store.project.projectName).toBe('当前会话项目')
  })

  it('预检期间刷新明细不会令prechecking永久卡住', async () => {
    api.getProjectProgress.mockResolvedValue({ data: progress() })
    const pending = deferred()
    api.getCompletionPrecheck.mockReturnValue(pending.promise)
    const store = useProjectProgressStore()
    await store.load(12)
    const checking = store.precheckCompletion()
    await store.search()
    pending.resolve({ data: completionPrecheck() })
    await checking
    expect(store.prechecking).toBe(false)
    expect(store.precheck.canComplete).toBe(true)
  })

  it('快速连续筛选以最后一次请求和响应为准', async () => {
    api.getProjectProgress.mockResolvedValueOnce({ data: progress() })
    const draft = deferred()
    const submitted = deferred()
    api.getProjectProgress.mockReturnValueOnce(draft.promise).mockReturnValueOnce(submitted.promise)
    const store = useProjectProgressStore()
    await store.load(12)
    store.filters.status = 'DRAFT'
    const first = store.search()
    store.filters.status = 'SUBMITTED'
    const second = store.search()
    submitted.resolve({ data: progress({ rows: [{ assignmentId: 2, status: 'SUBMITTED' }] }) })
    await second
    draft.resolve({ data: progress({ rows: [{ assignmentId: 1, status: 'DRAFT' }] }) })
    await first
    expect(api.getProjectProgress).toHaveBeenCalledTimes(3)
    expect(store.filters.status).toBe('SUBMITTED')
    expect(store.rows).toEqual([{ assignmentId: 2, status: 'SUBMITTED' }])
  })

  it('旧进度请求的迟到失败按epoch丢弃且不会覆盖新项目', async () => {
    const old = deferred()
    api.getProjectProgress
      .mockReturnValueOnce(old.promise)
      .mockResolvedValueOnce({ data: progress({ projectId: 13, projectName: '当前项目' }) })
    const store = useProjectProgressStore()
    const oldLoad = store.load(12)
    await store.load(13)

    old.reject(new Error('旧项目迟到失败'))

    await expect(oldLoad).resolves.toBeNull()
    expect(store.projectId).toBe(13)
    expect(store.project.projectName).toBe('当前项目')
  })

  it('旧预检请求的迟到失败按epoch丢弃且不清除新项目预检', async () => {
    api.getProjectProgress
      .mockResolvedValueOnce({ data: progress() })
      .mockResolvedValueOnce({ data: progress({ projectId: 13, projectName: '当前项目' }) })
    const old = deferred()
    api.getCompletionPrecheck
      .mockReturnValueOnce(old.promise)
      .mockResolvedValueOnce({ data: completionPrecheck({ projectId: 13, projectName: '当前项目' }) })
    const store = useProjectProgressStore()
    await store.load(12)
    const oldPrecheck = store.precheckCompletion()
    await store.load(13)
    await store.precheckCompletion()

    old.reject(new Error('旧预检迟到失败'))

    await expect(oldPrecheck).resolves.toBeNull()
    expect(store.precheck.projectId).toBe(13)
  })

  it('完成成功即使刷新失败也立即进入只读完成态并保留最终统计', async () => {
    api.getProjectProgress.mockResolvedValueOnce({ data: progress() }).mockRejectedValueOnce(new Error('刷新失败'))
    api.getCompletionPrecheck.mockResolvedValue({ data: completionPrecheck() })
    api.completeProject.mockResolvedValue({ data: {
      projectId: 12,
      projectStatus: 'COMPLETED',
      projectLockVersion: 4,
      completionReason: '本轮截止',
      alreadyCompleted: false,
      summary: summary({ draftCount: 0, pendingCount: 0, closedIncompleteCount: 4 })
    } })
    api.getProject.mockRejectedValue(new Error('详情刷新失败'))
    const store = useProjectProgressStore()
    await store.load(12)
    await store.precheckCompletion()
    await store.complete('本轮截止')
    expect(store.project.projectStatus).toBe('COMPLETED')
    expect(store.summary.closedIncompleteCount).toBe(4)
    expect(store.completionIssue.code).toBe('COMPLETION_REFRESH_FAILED')
  })

  it('预检发现数据范围收窄时立即清除旧人员明细并展示固定范围提示', async () => {
    api.getProjectProgress.mockResolvedValue({ data: progress() })
    api.getCompletionPrecheck.mockResolvedValue({
      data: completionPrecheck({ dataScopeComplete: false, canComplete: false })
    })
    const store = useProjectProgressStore()
    await store.load(12)

    await store.precheckCompletion()

    expect(store.project.projectId).toBe(12)
    expect(store.summary).toEqual(summary())
    expect(store.dataScopeComplete).toBe(false)
    expect(store.scopeMessage).toBe('当前数据范围仅覆盖部分被评价人')
    expect(store.relations).toEqual([])
    expect(store.rows).toEqual([])
    expect(store.total).toBe(0)
    expect(store.detailsStale).toBe(true)
  })

  it.each([403, 404])('完成预检返回%s时立即清空旧项目统计和人员明细', async status => {
    api.getProjectProgress.mockResolvedValue({ data: progress() })
    api.getCompletionPrecheck.mockRejectedValue(Object.assign(new Error('资源已不可见'), { status }))
    const store = useProjectProgressStore()
    await store.load(12)

    await expect(store.precheckCompletion()).rejects.toThrow('资源已不可见')

    expect(store.project).toBeNull()
    expect(store.summary).toBeNull()
    expect(store.relations).toEqual([])
    expect(store.rows).toEqual([])
    expect(store.total).toBe(0)
    expect(store.dataScopeComplete).toBe(false)
    expect(store.projectDetail).toBeNull()
  })

  it('未知403不伪装为局部数据范围错误', async () => {
    api.getProjectProgress.mockResolvedValue({ data: progress() })
    api.getCompletionPrecheck.mockResolvedValue({ data: completionPrecheck() })
    api.completeProject.mockRejectedValue(Object.assign(new Error('权限已撤销'), { status: 403, data: { code: 'FORBIDDEN' } }))
    const store = useProjectProgressStore()
    await store.load(12)
    await store.precheckCompletion()
    await expect(store.complete('本轮截止')).rejects.toThrow('权限已撤销')
    expect(store.project).toBeNull()
    expect(store.summary).toBeNull()
    expect(store.rows).toEqual([])
    expect(store.dataScopeComplete).toBe(false)
    expect(store.scopeMessage).toBeNull()
    expect(store.completionIssue).toEqual({ code: 'FORBIDDEN', message: '权限已撤销' })
  })

  it('旧完成请求的迟到错误不能污染新项目或解除新操作防重入', async () => {
    api.getProjectProgress.mockResolvedValue({ data: progress() })
    api.getCompletionPrecheck.mockResolvedValue({ data: completionPrecheck() })
    const oldComplete = deferred()
    api.completeProject.mockReturnValue(oldComplete.promise)
    const store = useProjectProgressStore()
    await store.load(12)
    await store.precheckCompletion()
    const completing = store.complete('旧项目完成原因')
    await store.load(13)
    store.precheck = completionPrecheck({ projectId: 13, projectName: '当前项目' })
    store.completing = true
    oldComplete.reject(Object.assign(new Error('旧请求迟到403'), { status: 403, data: { code: 'FORBIDDEN' } }))
    await expect(completing).resolves.toBeNull()
    expect(store.projectId).toBe(13)
    expect(store.project.projectName).toBe('年度反馈')
    expect(store.precheck.projectId).toBe(13)
    expect(store.completionIssue).toBeNull()
    expect(store.completing).toBe(true)
  })

  it.each([403, 404])('进度刷新返回%s时立即清空旧项目统计和人员明细', async status => {
    api.getProjectProgress
      .mockResolvedValueOnce({ data: progress() })
      .mockRejectedValueOnce(Object.assign(new Error('资源已不可见'), { status }))
    const store = useProjectProgressStore()
    await store.load(12)

    await expect(store.load(12)).rejects.toThrow('资源已不可见')

    expect(store.project).toBeNull()
    expect(store.summary).toBeNull()
    expect(store.relations).toEqual([])
    expect(store.rows).toEqual([])
    expect(store.total).toBe(0)
    expect(store.projectDetail).toBeNull()
  })

  it('核对请求被并发筛选抢占时保持完成结果未知锁定', async () => {
    const verification = deferred()
    api.getProjectProgress
      .mockResolvedValueOnce({ data: progress() })
      .mockReturnValueOnce(verification.promise)
      .mockResolvedValueOnce({ data: progress({ rows: [], total: 0 }) })
    const store = useProjectProgressStore()
    await store.load(12)
    store.completionResultUnknown = true
    store.completionIssue = { code: 'COMPLETION_RESULT_UNKNOWN', message: '等待核对' }

    const rechecking = store.recheckCompletionResult()
    await store.search()
    verification.resolve({ data: progress() })

    await expect(rechecking).resolves.toBeNull()
    expect(store.completionResultUnknown).toBe(true)
    expect(store.completionIssue.code).toBe('COMPLETION_RESULT_UNKNOWN')
  })

  it('预检请求发送前失败时保存明确的页面错误', async () => {
    api.getProjectProgress.mockResolvedValue({ data: progress() })
    api.getCompletionPrecheck.mockRejectedValue(Object.assign(new Error('请求加密失败'), {
      kind: 'REQUEST_SETUP',
      requestSent: false,
      status: 0
    }))
    const store = useProjectProgressStore()
    await store.load(12)

    await expect(store.precheckCompletion()).rejects.toThrow('请求加密失败')

    expect(store.completionIssue).toEqual({ code: 'REQUEST_SETUP', message: '请求加密失败' })
  })

  it('完成请求422失败时保存明确的页面错误且不伪装结果未知', async () => {
    api.getProjectProgress.mockResolvedValue({ data: progress() })
    api.getCompletionPrecheck.mockResolvedValue({ data: completionPrecheck() })
    api.completeProject.mockRejectedValue(Object.assign(new Error('完成原因不合法'), {
      status: 422,
      data: { code: 'VALIDATION_ERROR' },
      requestSent: true
    }))
    const store = useProjectProgressStore()
    await store.load(12)
    await store.precheckCompletion()

    await expect(store.complete('本轮截止')).rejects.toThrow('完成原因不合法')

    expect(store.completionResultUnknown).toBe(false)
    expect(store.completionIssue).toEqual({ code: 'VALIDATION_ERROR', message: '完成原因不合法' })
  })
})
