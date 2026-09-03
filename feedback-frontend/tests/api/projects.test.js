import { beforeEach, describe, expect, it, vi } from 'vitest'

const request = vi.fn()
vi.mock('@/utils/request', () => ({ default: request }))

const {
  completeProject,
  createProject,
  getCompletionPrecheck,
  getProjectProgress,
  getPublicationConfig,
  getQuestionnaireDraft,
  listProjects,
  listParticipantOptions,
  publishProject,
  removeProject,
  savePublicationConfig,
  saveQuestionnaireDraft,
  updateProject
} = await import('@/api/feedback/projects')

describe('评价项目API', () => {
  beforeEach(() => request.mockReset())

  it('项目CRUD使用固定feedback接口和乐观锁参数', async () => {
    await listProjects({ pageNum: 1 })
    await createProject({ projectName: '年度评价' })
    await updateProject(12, { projectName: '年度评价（更新）', lockVersion: 1 })
    await removeProject(12, 2)

    expect(request).toHaveBeenNthCalledWith(1, {
      url: '/feedback/projects',
      method: 'get',
      params: { pageNum: 1 }
    })
    expect(request).toHaveBeenNthCalledWith(2, {
      url: '/feedback/projects',
      method: 'post',
      data: { projectName: '年度评价' }
    })
    expect(request).toHaveBeenNthCalledWith(4, {
      url: '/feedback/projects/12',
      method: 'delete',
      params: { lockVersion: 2 }
    })
  })

  it('问卷草稿读取与保存是两个明确接口调用', async () => {
    const draft = { versionId: 8, lockVersion: 3, pages: [] }
    await getQuestionnaireDraft(12)
    await saveQuestionnaireDraft(12, draft)

    expect(request).toHaveBeenNthCalledWith(1, {
      url: '/feedback/projects/12/questionnaire-draft',
      method: 'get'
    })
    expect(request).toHaveBeenNthCalledWith(2, {
      url: '/feedback/projects/12/questionnaire-draft',
      method: 'put',
      data: draft,
      headers: { repeatInterval: 1500 }
    })
  })

  it('P5人员、聚合配置和发布使用固定接口及防重复提交间隔', async () => {
    const config = { projectLockVersion: 2, versionId: 8, versionLockVersion: 3 }
    await listParticipantOptions(12, { pageNum: 1, keyword: '张' })
    await getPublicationConfig(12)
    await savePublicationConfig(12, config)
    await publishProject(12, config)

    expect(request).toHaveBeenNthCalledWith(1, {
      url: '/feedback/projects/12/participant-options',
      method: 'get',
      params: { pageNum: 1, keyword: '张' }
    })
    expect(request).toHaveBeenNthCalledWith(2, {
      url: '/feedback/projects/12/publication-config',
      method: 'get'
    })
    expect(request).toHaveBeenNthCalledWith(3, {
      url: '/feedback/projects/12/publication-config',
      method: 'put',
      data: config,
      headers: { repeatInterval: 1500 }
    })
    expect(request).toHaveBeenNthCalledWith(4, {
      url: '/feedback/projects/12/publish',
      method: 'post',
      data: config,
      headers: { repeatInterval: 3000 }
    })
  })

  it('P7进度、实时预检和完成使用精确接口契约', async () => {
    const params = {
      pageNum: 2,
      pageSize: 20,
      evaluatorUserId: 12,
      targetUserId: 21,
      relationId: 8,
      status: 'DRAFT',
      evaluatorKeyword: '张',
      targetKeyword: '李'
    }
    const payload = {
      projectLockVersion: 3,
      completionReason: '本轮评价截止',
      expectedSummary: {
        totalCount: 10,
        submittedCount: 6,
        draftCount: 2,
        pendingCount: 2,
        closedIncompleteCount: 0
      }
    }
    const progressEnvelope = {
      code: 200,
      msg: '操作成功',
      data: {
        projectId: 12,
        projectName: '年度反馈',
        projectStatus: 'ACTIVE',
        projectLockVersion: 3,
        dataScopeComplete: true,
        scopeMessage: null,
        summary: { ...payload.expectedSummary, incompleteCount: 4, completionRate: '60.00' },
        filterOptions: { relations: [{ relationId: 8, relationCode: 'PEER', relationName: '同级', sortOrder: 2 }] },
        rows: [{ assignmentId: 101, evaluatorUserId: 12, evaluatorName: '张三', evaluatorDeptName: '研发部', targetUserId: 21, targetName: '李四', targetDeptId: 5, targetDeptName: '产品部', relationId: 8, relationCode: 'PEER', relationName: '同级', status: 'DRAFT', savedTime: '2026-09-02T10:00:00', submittedTime: null, closedTime: null }],
        total: 1,
        pageNum: 2,
        pageSize: 20
      }
    }
    const precheckEnvelope = {
      code: 200,
      msg: '操作成功',
      data: {
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
        summary: progressEnvelope.data.summary,
        missingRelations: [{ targetUserId: 21, targetName: '李四', relationId: 8, relationName: '同级', assignmentCount: 2, submittedCount: 0 }],
        impactMessages: ['完成后未提交任务将关闭。'],
        precheckedAt: '2026-09-02T10:05:00'
      }
    }
    const completeEnvelope = {
      code: 200,
      msg: '项目已完成',
      data: {
        projectId: 12,
        projectStatus: 'COMPLETED',
        projectLockVersion: 4,
        completedBy: 7,
        completedTime: '2026-09-02T10:06:00',
        completionReason: '本轮评价截止',
        alreadyCompleted: false,
        summary: { totalCount: 10, submittedCount: 6, draftCount: 0, pendingCount: 0, closedIncompleteCount: 4, incompleteCount: 4, completionRate: '60.00' }
      }
    }
    request
      .mockResolvedValueOnce(progressEnvelope)
      .mockResolvedValueOnce(precheckEnvelope)
      .mockResolvedValueOnce(completeEnvelope)

    const progressResponse = await getProjectProgress(12, params)
    const precheckResponse = await getCompletionPrecheck(12)
    const completeResponse = await completeProject(12, payload)

    expect(request).toHaveBeenNthCalledWith(1, {
      url: '/feedback/projects/12/progress',
      method: 'get',
      params,
      suppressErrorMessage: true
    })
    expect(request).toHaveBeenNthCalledWith(2, {
      url: '/feedback/projects/12/completion-precheck',
      method: 'get',
      suppressErrorMessage: true
    })
    expect(request).toHaveBeenNthCalledWith(3, {
      url: '/feedback/projects/12/complete',
      method: 'post',
      data: payload,
      headers: { repeatInterval: 3000 },
      suppressErrorMessage: true
    })
    expect(progressResponse).toEqual(progressEnvelope)
    expect(precheckResponse).toEqual(precheckEnvelope)
    expect(completeResponse).toEqual(completeEnvelope)
    expect(Object.keys(precheckResponse.data)).toEqual([
      'projectId', 'projectName', 'projectStatus', 'projectLockVersion', 'dataScopeComplete',
      'canComplete', 'completedBy', 'completedTime', 'completionReason', 'alreadyCompleted',
      'summary', 'missingRelations', 'impactMessages', 'precheckedAt'
    ])
    expect(precheckResponse.data).not.toHaveProperty('rows')
    expect(precheckResponse.data).not.toHaveProperty('filterOptions')
  })
})
