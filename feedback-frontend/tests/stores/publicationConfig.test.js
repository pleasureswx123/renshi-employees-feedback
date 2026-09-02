import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const getPublicationConfig = vi.fn()
const listParticipantOptions = vi.fn()
const publishProject = vi.fn()
const savePublicationConfig = vi.fn()
vi.mock('@/api/feedback/projects', () => ({
  getPublicationConfig,
  listParticipantOptions,
  publishProject,
  savePublicationConfig
}))

const { usePublicationConfigStore } = await import('@/stores/publicationConfig')

function configFixture(overrides = {}) {
  return {
    projectId: 7,
    projectName: 'P5测试项目',
    projectStatus: 'PREPARING',
    projectLockVersion: 2,
    versionId: 8,
    versionLockVersion: 3,
    versionStatus: 'DRAFT',
    editable: true,
    targets: [],
    relations: [
      {
        relationId: 1,
        relationCode: 'REL_PEER',
        relationType: 'PEER',
        relationName: '同级',
        isEnabled: false,
        participatesInScore: false,
        weight: '0.0000',
        sortOrder: 1,
        fixed: true
      },
      {
        relationId: 2,
        relationCode: 'REL_SELF',
        relationType: 'SELF',
        relationName: '自己',
        isEnabled: true,
        participatesInScore: false,
        weight: '0.0000',
        sortOrder: 2,
        fixed: true
      }
    ],
    evaluatorSelections: [],
    configuredParticipants: [],
    preview: { targetCount: 0, evaluatorCount: 0, assignmentCount: 0, targetSummaries: [] },
    validationIssues: [{ code: 'TARGET_REQUIRED', path: 'targets', message: '至少选择一人' }],
    isPublishReady: false,
    ...overrides
  }
}

describe('P5发布配置Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getPublicationConfig.mockReset()
    listParticipantOptions.mockReset()
    publishProject.mockReset()
    savePublicationConfig.mockReset()
  })

  it('分页加载候选、选择目标和评价人，并过滤自评提交', async () => {
    getPublicationConfig.mockResolvedValue({ data: configFixture() })
    listParticipantOptions.mockResolvedValue({
      rows: [
        { userId: 10, userName: 'zhang', nickName: '张三', available: true },
        { userId: 11, userName: 'li', nickName: '李四', available: true }
      ],
      total: 2
    })
    const store = usePublicationConfigStore()
    await store.load(7)
    await store.loadCandidates({ keyword: '张' })
    store.addTarget(store.candidateRows[0])
    store.updateRelation('REL_PEER', {
      isEnabled: true,
      participatesInScore: true,
      weight: '100.0000'
    })
    store.setEvaluatorIds(10, 'REL_PEER', [10, 11])

    const saved = configFixture({
      projectLockVersion: 3,
      versionLockVersion: 4,
      targets: [{ ...store.candidateRows[0], targetId: 20, onlySelfEvaluation: false }],
      evaluatorSelections: [
        { targetUserId: 10, relationCode: 'REL_PEER', evaluatorUserIds: [11] },
        { targetUserId: 10, relationCode: 'REL_SELF', evaluatorUserIds: [10], systemManaged: true }
      ],
      preview: { targetCount: 1, evaluatorCount: 2, assignmentCount: 2, targetSummaries: [] },
      validationIssues: [],
      isPublishReady: true
    })
    savePublicationConfig.mockResolvedValue({ data: saved })
    await store.save()

    expect(listParticipantOptions).toHaveBeenCalledWith(
      7,
      expect.objectContaining({ pageNum: 1, pageSize: 10, keyword: '张' })
    )
    expect(savePublicationConfig.mock.calls[0][1].evaluatorSelections).toEqual([
      { targetUserId: 10, relationCode: 'REL_PEER', evaluatorUserIds: [11] }
    ])
    expect(store.dirty).toBe(false)
    expect(store.config.preview.assignmentCount).toBe(2)
  })

  it('未保存时禁止发布，发布成功后重新读取冻结配置', async () => {
    const ready = configFixture({ isPublishReady: true, validationIssues: [] })
    getPublicationConfig.mockResolvedValueOnce({ data: ready }).mockResolvedValueOnce({
      data: configFixture({
        ...ready,
        projectStatus: 'ACTIVE',
        versionStatus: 'FROZEN',
        editable: false
      })
    })
    publishProject.mockResolvedValue({ data: { assignmentCount: 2, alreadyPublished: false } })
    const store = usePublicationConfigStore()
    await store.load(7)
    store.markDirty()

    await expect(store.publish()).rejects.toThrow('请先保存当前修改')
    store.dirty = false
    const result = await store.publish()

    expect(publishProject).toHaveBeenCalledWith(7, {
      projectLockVersion: 2,
      versionId: 8,
      versionLockVersion: 3
    })
    expect(result.assignmentCount).toBe(2)
    expect(store.config.editable).toBe(false)
  })

  it('发布校验冲突时保留后端稳定问题并禁止继续发布', async () => {
    const ready = configFixture({ isPublishReady: true, validationIssues: [] })
    const conflict = Object.assign(new Error('发布前检查未通过'), {
      status: 409,
      data: {
        validationIssues: [
          { code: 'EVALUATOR_REQUIRED', path: 'evaluatorSelections', message: '请为同级关系选择评价人' }
        ]
      }
    })
    getPublicationConfig.mockResolvedValue({ data: ready })
    publishProject.mockRejectedValue(conflict)
    const store = usePublicationConfigStore()
    await store.load(7)

    await expect(store.publish()).rejects.toBe(conflict)

    expect(store.config.validationIssues).toEqual(conflict.data.validationIssues)
    expect(store.config.isPublishReady).toBe(false)
    expect(store.publishing).toBe(false)
  })

  it('发布请求未完成时忽略重复点击', async () => {
    const ready = configFixture({ isPublishReady: true, validationIssues: [] })
    let resolvePublish
    const pendingPublish = new Promise(resolve => { resolvePublish = resolve })
    getPublicationConfig.mockResolvedValueOnce({ data: ready }).mockResolvedValueOnce({
      data: configFixture({ ...ready, projectStatus: 'ACTIVE', versionStatus: 'FROZEN', editable: false })
    })
    publishProject.mockReturnValue(pendingPublish)
    const store = usePublicationConfigStore()
    await store.load(7)

    const first = store.publish()
    const duplicate = await store.publish()
    resolvePublish({ data: { assignmentCount: 2, alreadyPublished: false } })
    await first

    expect(duplicate).toBeNull()
    expect(publishProject).toHaveBeenCalledTimes(1)
  })
})
