import { beforeEach, describe, expect, it, vi } from 'vitest'

const request = vi.fn()
vi.mock('@/utils/request', () => ({ default: request }))

const {
  createProject,
  getQuestionnaireDraft,
  listProjects,
  removeProject,
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
})
