import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { completeAnswers, detailFixture } from '../fixtures/answerSheet'

const api = vi.hoisted(() => ({ getMyTask: vi.fn(), getMyHistory: vi.fn(), saveMyDraft: vi.fn(), submitMyAnswer: vi.fn() }))
vi.mock('@/api/feedback/tasks', () => api)
const { useAnswerSheetStore } = await import('@/stores/answerSheet')
const { useAuthStore } = await import('@/stores/auth')

function deferred() {
  let resolve
  const promise = new Promise(done => { resolve = done })
  return { promise, resolve }
}

describe('逐任务答卷Store', () => {
  beforeEach(() => { setActivePinia(createPinia()); Object.values(api).forEach(fn => fn.mockReset()) })

  it('暂存后水合锁版本、答案及最近页面，重新加载可恢复', async () => {
    api.getMyTask.mockResolvedValue({ data: detailFixture() })
    const store = useAnswerSheetStore()
    await store.load(1)
    store.setAnswer('Q1', { optionCode: 'O1', reason: '' })
    store.setPage(1)
    const saved = detailFixture(1, { lockVersion: 1, lastPageId: 22, answers: [{ questionId: 1, optionId: 11, reason: null }] })
    api.saveMyDraft.mockResolvedValue({ data: saved })
    await store.save()
    expect(api.saveMyDraft.mock.calls[0][1]).toMatchObject({ versionId: 20, lockVersion: 0, lastPageId: 22 })
    expect(store.dirty).toBe(false)
    expect(store.detail.lockVersion).toBe(1)
    api.getMyTask.mockResolvedValue({ data: saved })
    await store.load(1)
    expect(store.pageIndex).toBe(1)
    expect(store.answers.Q1.optionCode).toBe('O1')
  })

  it('缺必答题不能调用提交接口；超时重试沿用同一幂等请求', async () => {
    api.getMyTask.mockResolvedValue({ data: detailFixture() })
    const store = useAnswerSheetStore()
    await store.load(1)
    expect(await store.submit()).toBeNull()
    expect(api.submitMyAnswer).not.toHaveBeenCalled()
    Object.entries(completeAnswers()).forEach(([key, value]) => store.setAnswer(key, value))
    api.submitMyAnswer.mockRejectedValueOnce(new Error('超时')).mockResolvedValueOnce({ data: detailFixture(1, { editable: false }) })
    await store.submit()
    const first = api.submitMyAnswer.mock.calls[0][1]
    expect(first.submissionId).toMatch(/^[0-9a-f-]{36}$/)
    await store.submit()
    expect(api.submitMyAnswer.mock.calls[1][1]).toEqual(first)
    expect(store.editable).toBe(false)
  })

  it('请求进行时阻止重复写入和修改，冲突保留本地输入并要求重新加载', async () => {
    api.getMyTask.mockResolvedValue({ data: detailFixture() })
    const store = useAnswerSheetStore()
    await store.load(1)
    store.setAnswer('Q5', { text: '草稿' })
    const pending = deferred()
    api.saveMyDraft.mockReturnValue(pending.promise)
    const first = store.save()
    expect(await store.save()).toBeNull()
    store.setAnswer('Q5', { text: '迟到输入' })
    expect(store.answers.Q5.text).toBe('草稿')
    pending.resolve({ data: detailFixture() })
    await first
    store.setAnswer('Q5', { text: '本地保留' })
    api.saveMyDraft.mockRejectedValue(Object.assign(new Error('版本冲突'), { data: { code: 'ANSWER_VERSION_CONFLICT' } }))
    await store.save()
    expect(store.conflict).toBe(true)
    expect(store.answers.Q5.text).toBe('本地保留')
    expect(await store.submit()).toBeNull()
  })

  it('任务切换忽略旧读取和旧保存响应', async () => {
    const old = deferred()
    api.getMyTask.mockReturnValueOnce(old.promise).mockResolvedValue({ data: detailFixture(2) })
    const store = useAnswerSheetStore()
    const loadOld = store.load(1)
    await store.load(2)
    old.resolve({ data: detailFixture(1) })
    await loadOld
    expect(store.assignmentId).toBe(2)
    expect(store.detail.task.targetName).toBe('李四')
    const saveOld = deferred()
    api.saveMyDraft.mockReturnValue(saveOld.promise)
    const saving = store.save()
    api.getMyTask.mockResolvedValue({ data: detailFixture(3) })
    await store.load(3)
    saveOld.resolve({ data: detailFixture(2) })
    await saving
    expect(store.detail.task.assignmentId).toBe(3)
  })

  it('退出登录清空敏感答案，旧响应不能重新填充Store', async () => {
    const pending = deferred()
    api.getMyTask.mockReturnValue(pending.promise)
    const store = useAnswerSheetStore()
    const loading = store.load(1)
    useAuthStore().clearSession()
    pending.resolve({ data: detailFixture() })
    await loading
    expect(store.detail).toBeNull()
    expect(store.answers).toEqual({})
  })

  it('历史永远只读，关闭错误停止后续写入', async () => {
    api.getMyHistory.mockResolvedValue({ data: detailFixture(1, { editable: true }) })
    const store = useAnswerSheetStore()
    await store.load(1, { history: true })
    store.setAnswer('Q5', { text: '不能修改' })
    expect(store.answers.Q5.text).toBe('')
    expect(await store.save()).toBeNull()
    api.getMyTask.mockResolvedValue({ data: detailFixture() })
    await store.load(1)
    api.saveMyDraft.mockRejectedValue(Object.assign(new Error('项目已完成'), { data: { code: 'PROJECT_CLOSED' } }))
    await store.save()
    expect(store.editable).toBe(false)
  })
})
