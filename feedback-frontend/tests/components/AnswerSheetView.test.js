import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, RouterView } from 'vue-router'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus, { ElMessage, ElMessageBox } from 'element-plus'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import AnswerSheetView from '@/views/employee/AnswerSheetView.vue'
import { useAnswerSheetStore } from '@/stores/answerSheet'
import { useAuthStore } from '@/stores/auth'
import { completeAnswers, detailFixture } from '../fixtures/answerSheet'

const api = vi.hoisted(() => ({ getMyTask: vi.fn(), getMyHistory: vi.fn(), saveMyDraft: vi.fn(), submitMyAnswer: vi.fn() }))
vi.mock('@/api/feedback/tasks', () => api)

let wrapper
let pinia
const button = label => wrapper.findAll('button').find(item => item.text() === label)

async function open(history = false) {
  const router = createRouter({ history: createMemoryHistory(), routes: [
    { path: '/tasks/:assignmentId', component: AnswerSheetView, props: { history } },
    { path: '/employee/todos', component: { template: '<div>我的待办列表</div>' } },
    { path: '/other', component: { template: '<div>其他页面</div>' } }
  ] })
  await router.push('/tasks/1')
  await router.isReady()
  wrapper = mount(RouterView, { attachTo: document.body, global: { plugins: [pinia, router, ElementPlus] } })
  await flushPromises()
  return { store: useAnswerSheetStore(), router }
}

describe('真实Element Plus答题表单', () => {
  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    const auth = useAuthStore()
    auth.token = 'test-token'
    auth.permissions = ['feedback:task:view', 'feedback:task:answer', 'feedback:task:submit', 'feedback:history:view']
    Object.values(api).forEach(fn => fn.mockReset())
    api.getMyTask.mockResolvedValue({ data: detailFixture() })
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm')
    Element.prototype.scrollIntoView = vi.fn()
  })
  afterEach(() => { wrapper?.unmount(); ElMessage.closeAll(); document.body.innerHTML = '' })

  it.each([false, true])('答题和历史页面忽略旧页面说明，保留统一问卷说明与分页（历史=%s）', async history => {
    const detail = detailFixture()
    detail.lastPageId = history ? 22 : 21
    detail.questionnaire.description = '统一问卷说明'
    detail.questionnaire.pages.forEach(page => { page.pageDescription = '已停用的页面说明' })
    api.getMyTask.mockResolvedValue({ data: detail })
    api.getMyHistory.mockResolvedValue({ data: detail })
    const { store } = await open(history)

    expect(store.pageIndex).toBe(0)
    expect(wrapper.findAll('.answer-page')[0].isVisible()).toBe(true)
    expect(wrapper.text()).toContain('统一问卷说明')
    expect(wrapper.text()).not.toContain('已停用的页面说明')
    expect(wrapper.find('.answer-document .answer-progress').exists()).toBe(false)
    expect(wrapper.find('[aria-label="问卷页面"]').exists()).toBe(false)
    expect(wrapper.find('.answer-page h3').exists()).toBe(false)
    expect(wrapper.find('.answer-question-heading').text()).toContain('第 1 题：协作评价')
    await button('下一页').trigger('click')
    expect(store.pageIndex).toBe(1)
    expect(wrapper.findAll('.answer-page')[1].text()).toContain('第 3 题：质量评分')
    expect(wrapper.text()).toContain('统一问卷说明')
    expect(wrapper.text()).not.toContain('已停用的页面说明')
    if (history) {
      await button('重新加载').trigger('click')
      await flushPromises()
      expect(store.pageIndex).toBe(0)
      expect(wrapper.findAll('.answer-page')[0].isVisible()).toBe(true)
      expect(button('上一页').element.disabled).toBe(true)
    }
  })

  it('提交校验会从第二页定位第一道缺答题，不弹确认框或发送请求', async () => {
    const { store } = await open()
    await button('下一页').trigger('click')
    await button('提交本份评价').trigger('click')
    await flushPromises()
    expect(store.pageIndex).toBe(0)
    await vi.waitFor(() => expect(wrapper.findAll('.el-form-item__error').length).toBeGreaterThan(0))
    expect(wrapper.text()).toContain('请检查以下题目')
    expect(wrapper.text()).toContain('协作 · 协作评价：请完成这道必答题')
    expect(ElMessageBox.confirm).not.toHaveBeenCalled()
    expect(api.submitMyAnswer).not.toHaveBeenCalled()
    expect(button('提交本份评价').element.disabled).toBe(false)
  })

  it('不完整答案可以暂存，发送正确任务和页面版本并显示保存状态', async () => {
    const { store } = await open()
    await wrapper.findAll('input[type="radio"]')[0].setValue(true)
    expect(wrapper.find('.el-radio.is-bordered').exists()).toBe(false)
    await button('下一页').trigger('click')
    api.saveMyDraft.mockResolvedValue({ data: detailFixture(1, {
      lockVersion: 1, lastPageId: 22, answers: [{ questionId: 1, optionId: 11 }],
      task: { ...detailFixture().task, status: 'DRAFT', savedTime: '2026-09-02T18:00:00' }
    }) })
    await button('暂存答卷').trigger('click')
    await flushPromises()
    expect(api.saveMyDraft).toHaveBeenCalledWith(1, expect.objectContaining({ lastPageId: 22, lockVersion: 0 }))
    expect(store.answeredCount).toBe(1)
    expect(store.dirty).toBe(false)
    expect(wrapper.text()).toContain('最近保存：2026-09-02 18:00:00')
    expect(ElMessageBox.confirm).not.toHaveBeenCalled()
  })

  it('只有确认后提交，确认等待期间禁用重复操作，成功返回我的待办且不触发未暂存提示', async () => {
    const { store, router } = await open()
    Object.entries(completeAnswers()).forEach(([code, answer]) => store.setAnswer(code, answer))
    let confirm
    ElMessageBox.confirm.mockImplementation(() => new Promise(resolve => { confirm = resolve }))
    api.submitMyAnswer.mockResolvedValue({ data: detailFixture(1, {
      editable: false, task: { ...detailFixture().task, status: 'SUBMITTED' }
    }) })
    await button('提交本份评价').trigger('click')
    await flushPromises()
    expect(ElMessageBox.confirm).toHaveBeenCalledOnce()
    expect(button('提交本份评价').element.disabled).toBe(true)
    expect(api.submitMyAnswer).not.toHaveBeenCalled()
    confirm('confirm')
    await flushPromises()
    expect(api.submitMyAnswer).toHaveBeenCalledOnce()
    expect(router.currentRoute.value.path).toBe('/employee/todos')
    expect(wrapper.text()).toContain('我的待办列表')
    expect(ElMessageBox.confirm).toHaveBeenCalledOnce()
    expect(store.answers).toEqual({})
    expect(button('暂存答卷')).toBeUndefined()
    expect(button('提交本份评价')).toBeUndefined()
  })

  it.each(['cancel', 'failure'])('取消确认或提交失败时保留答案并停留在答题页：%s', async outcome => {
    const { store, router } = await open()
    Object.entries(completeAnswers()).forEach(([code, answer]) => store.setAnswer(code, answer))
    if (outcome === 'cancel') ElMessageBox.confirm.mockRejectedValue('cancel')
    else api.submitMyAnswer.mockRejectedValue(new Error('提交失败，请重试'))
    await button('提交本份评价').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/tasks/1')
    expect(store.answers).toEqual(completeAnswers())
    expect(store.dirty).toBe(true)
    expect(button('提交本份评价').element.disabled).toBe(false)
    if (outcome === 'cancel') expect(api.submitMyAnswer).not.toHaveBeenCalled()
    else expect(wrapper.text()).toContain('提交失败，请重试')
  })

  it('未暂存离开可取消，历史模式永远不显示写入按钮', async () => {
    const { store, router } = await open()
    store.setAnswer('Q5', { text: '尚未保存' })
    ElMessageBox.confirm.mockRejectedValue('cancel')
    await router.push('/other')
    expect(router.currentRoute.value.path).toBe('/tasks/1')
    ElMessageBox.confirm.mockResolvedValue('confirm')
    await router.push('/other')
    await flushPromises()
    expect(store.answers).toEqual({})
    wrapper.unmount()
    api.getMyHistory.mockResolvedValue({ data: detailFixture(1, { editable: true }) })
    await open(true)
    expect(button('暂存答卷')).toBeUndefined()
    expect(button('提交本份评价')).toBeUndefined()
    expect(wrapper.findAll('input[type="radio"]')).toHaveLength(0)
  })
})
