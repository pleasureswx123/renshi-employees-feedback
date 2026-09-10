import ElementPlus, { ElMessage } from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, RouterView } from 'vue-router'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import ProjectProgressView from '@/views/hr/ProjectProgressView.vue'
import { useAuthStore } from '@/stores/auth'
import { useProjectProgressStore } from '@/stores/projectProgress'

const api = vi.hoisted(() => ({
  completeProject: vi.fn(),
  getCompletionPrecheck: vi.fn(),
  getProject: vi.fn(),
  getProjectProgress: vi.fn()
}))
vi.mock('@/api/feedback/projects', () => api)

const summary = {
  totalCount: 3,
  submittedCount: 1,
  draftCount: 1,
  pendingCount: 1,
  closedIncompleteCount: 0,
  incompleteCount: 2,
  completionRate: '33.33'
}

function progress(overrides = {}) {
  return {
    projectId: 12,
    projectName: '年度反馈',
    projectStatus: 'ACTIVE',
    projectLockVersion: 3,
    dataScopeComplete: true,
    scopeMessage: null,
    summary,
    filterOptions: { relations: [{ relationId: 8, relationCode: 'PEER', relationName: '同级', sortOrder: 1 }] },
    rows: [{ assignmentId: 1, evaluatorName: '张三', targetName: '李四', relationName: '同级', status: 'DRAFT' }],
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
    summary,
    missingRelations: [],
    impactMessages: ['完成后未提交任务将关闭。'],
    precheckedAt: '2026-09-02T10:05:00',
    ...overrides
  }
}

function completedPrecheck(overrides = {}) {
  return completionPrecheck({
    projectStatus: 'COMPLETED',
    projectLockVersion: 4,
    canComplete: false,
    completedBy: 7,
    completedTime: '2026-09-02T10:06:00',
    completionReason: '另一名HR已完成本轮评价',
    alreadyCompleted: true,
    summary: {
      totalCount: 3,
      submittedCount: 1,
      draftCount: 0,
      pendingCount: 0,
      closedIncompleteCount: 2,
      incompleteCount: 2,
      completionRate: '33.33'
    },
    impactMessages: ['项目已经完成，未提交任务已关闭。'],
    precheckedAt: '2026-09-02T10:06:01',
    ...overrides
  })
}

let wrapper
let pinia
async function open(permissions) {
  const auth = useAuthStore()
  auth.permissions = permissions
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/hr/projects/:projectId/progress', component: ProjectProgressView }]
  })
  await router.push('/hr/projects/12/progress')
  await router.isReady()
  wrapper = mount(RouterView, { attachTo: document.body, global: { plugins: [pinia, router, ElementPlus] } })
  await flushPromises()
}

function button(label) {
  return wrapper.findAll('button').find(item => item.attributes('aria-label') === label || item.text().includes(label))
}

describe('HR项目评价进度页', () => {
  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    Object.values(api).forEach(fn => fn.mockReset())
    api.getProjectProgress.mockResolvedValue({ data: progress() })
  })
  afterEach(() => { wrapper?.unmount(); ElMessage.closeAll(); document.body.innerHTML = '' })

  it('展示服务端项目状态、六张KPI、ElForm筛选与局部范围告警', async () => {
    api.getProjectProgress.mockResolvedValue({
      data: progress({ dataScopeComplete: false, scopeMessage: '当前数据范围仅覆盖部分被评价人' })
    })
    await open(['feedback:progress:view', 'feedback:project:complete'])

    expect(wrapper.text()).toContain('年度反馈')
    expect(wrapper.findAll('button.kpi-card')).toHaveLength(6)
    expect(wrapper.text()).toContain('当前数据范围仅覆盖部分被评价人')
    expect(wrapper.findComponent({ name: 'ElForm' }).exists()).toBe(true)
    expect(button('完成项目')).toBeUndefined()
    expect(button('提前结束')).toBeUndefined()
  })

  it('部分提交时禁用完成按钮，筛选不改变剩余数量，提前结束先预检再确认', async () => {
    const precheck = completionPrecheck()
    api.getCompletionPrecheck.mockResolvedValue({ data: precheck })
    await open(['feedback:progress:view', 'feedback:project:complete'])
    expect(button('完成项目').element.disabled).toBe(true)
    expect(wrapper.get('.completion-hint').text()).toBe('还有 2 份未提交')
    await button('完成项目').trigger('click')
    expect(api.getCompletionPrecheck).not.toHaveBeenCalled()

    const draftCard = wrapper.findAll('button.kpi-card')[2]
    await draftCard.trigger('click')
    await flushPromises()
    expect(api.getProjectProgress).toHaveBeenLastCalledWith(12, expect.objectContaining({ status: 'DRAFT', pageNum: 1 }))
    expect(wrapper.get('.completion-hint').text()).toBe('还有 2 份未提交')

    await button('提前结束').trigger('click')
    await flushPromises()
    expect(api.getCompletionPrecheck).toHaveBeenCalledWith(12)
    expect(document.body.textContent).toContain('提前结束项目确认')
    expect(document.body.textContent).toContain('完成后未提交任务将关闭。')
    expect(document.body.textContent).toContain('剩余 2 份任务将关闭')
    expect(document.body.textContent).toContain('报告仅使用 1 份已提交答卷')
    expect(api.completeProject).not.toHaveBeenCalled()
  })

  it('全部提交后启用完成入口，预检后仍需填写原因和确认', async () => {
    const full = { ...summary, submittedCount: 3, pendingCount: 0, draftCount: 0, incompleteCount: 0, completionRate: '100.00' }
    api.getProjectProgress.mockResolvedValue({ data: progress({ summary: full }) })
    api.getCompletionPrecheck.mockResolvedValue({ data: completionPrecheck({ summary: full }) })
    await open(['feedback:progress:view', 'feedback:project:complete'])
    expect(button('完成项目').element.disabled).toBe(false)
    expect(button('提前结束')).toBeUndefined()
    expect(wrapper.text()).toContain('全部评价已提交')
    await button('完成项目').trigger('click')
    await flushPromises()
    expect(document.body.textContent).toContain('完成项目实时预检')
    expect(document.body.textContent).not.toContain('确认提前结束')
    const confirmation = [...document.body.querySelectorAll('.completion-drawer button')].find(item => item.textContent.includes('确认完成项目'))
    expect(confirmation.disabled).toBe(true)
    expect(api.completeProject).not.toHaveBeenCalled()
  })

  it('暂无评价任务时禁止完成，也不提供提前结束入口', async () => {
    const empty = Object.fromEntries(Object.keys(summary).map(key => [key, key === 'completionRate' ? '0.00' : 0]))
    api.getProjectProgress.mockResolvedValue({ data: progress({ summary: empty, rows: [], total: 0 }) })
    await open(['feedback:progress:view', 'feedback:project:complete'])
    expect(button('完成项目').element.disabled).toBe(true)
    expect(button('提前结束')).toBeUndefined()
    expect(wrapper.text()).toContain('暂无可完成的评价任务')
  })

  it('提前结束预检发现最后任务已提交时，按最新数据切换为正常完成确认', async () => {
    const full = { ...summary, submittedCount: 3, pendingCount: 0, draftCount: 0, incompleteCount: 0, completionRate: '100.00' }
    let resolvePrecheck
    api.getCompletionPrecheck.mockReturnValue(new Promise(resolve => { resolvePrecheck = resolve }))
    await open(['feedback:progress:view', 'feedback:project:complete'])
    await button('提前结束').trigger('click')
    expect(button('提前结束').element.disabled).toBe(true)
    expect(button('完成项目').element.disabled).toBe(true)
    resolvePrecheck({ data: completionPrecheck({ summary: full }) })
    await flushPromises()
    expect(wrapper.text()).toContain('全部评价已提交')
    expect(button('提前结束')).toBeUndefined()
    expect(document.body.textContent).toContain('完成项目实时预检')
    expect(document.body.textContent).not.toContain('剩余 2 份任务将关闭')
    expect(api.completeProject).not.toHaveBeenCalled()
  })

  it('无完成权限或已完成项目只读且不显示完成入口', async () => {
    await open(['feedback:progress:view'])
    expect(button('完成项目')).toBeUndefined()
    expect(button('提前结束')).toBeUndefined()
    expect(button('返回评价进度入口')).toBeDefined()
    expect(button('返回项目列表')).toBeUndefined()
    wrapper.unmount()
    api.getProjectProgress.mockResolvedValue({ data: progress({ projectStatus: 'COMPLETED' }) })
    await open(['feedback:progress:view', 'feedback:project:complete'])
    expect(wrapper.text()).toContain('已完成')
    expect(button('完成项目')).toBeUndefined()
    expect(button('提前结束')).toBeUndefined()
    expect(wrapper.text()).not.toContain('重新打开')
  })

  it('预检发现项目已被并发完成时同步最终状态、刷新进度并打开只读完成抽屉', async () => {
    api.getProjectProgress
      .mockResolvedValueOnce({ data: progress() })
      .mockResolvedValueOnce({ data: progress({
        projectStatus: 'COMPLETED',
        projectLockVersion: 4,
        summary: completedPrecheck().summary
      }) })
    api.getCompletionPrecheck.mockResolvedValue({ data: completedPrecheck() })
    await open(['feedback:progress:view', 'feedback:project:complete'])

    await button('提前结束').trigger('click')
    await flushPromises()

    expect(api.getProjectProgress).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('已完成')
    expect(button('完成项目')).toBeUndefined()
    const drawer = document.body.querySelector('.completion-drawer')
    expect(drawer).not.toBeNull()
    expect(drawer.textContent).toContain('完成操作人ID：7')
    expect(drawer.textContent).toContain('完成时间：2026-09-02 10:06:00')
    expect(drawer.textContent).toContain('完成原因：另一名HR已完成本轮评价')
    expect(drawer.textContent).not.toContain('确认完成项目')
  })

  it('完成结果未知时锁定完成入口并只通过重新核对恢复实时预检', async () => {
    api.getProjectProgress.mockResolvedValue({ data: progress() })
    api.getCompletionPrecheck.mockResolvedValue({ data: completionPrecheck() })
    api.completeProject.mockRejectedValue(Object.assign(new Error('网关超时'), {
      kind: 'HTTP_SERVER',
      status: 504,
      requestSent: true
    }))
    await open(['feedback:progress:view', 'feedback:project:complete'])
    await button('提前结束').trigger('click')
    await flushPromises()
    const drawer = document.body.querySelector('.completion-drawer')
    const textarea = drawer.querySelector('textarea')
    textarea.value = '本轮截止'
    textarea.dispatchEvent(new Event('input'))
    drawer.querySelector('.el-checkbox').click()
    await flushPromises()
    ;[...drawer.querySelectorAll('button')].find(item => item.textContent.includes('确认提前结束')).click()
    await flushPromises()

    expect(button('重新核对')).toBeDefined()
    expect(button('完成项目').attributes('disabled')).toBeDefined()
    expect(button('提前结束').attributes('disabled')).toBeDefined()
    expect(api.completeProject).toHaveBeenCalledTimes(1)

    await button('重新核对').trigger('click')
    await flushPromises()

    expect(button('重新核对')).toBeUndefined()
    expect(button('提前结束').attributes('disabled')).toBeUndefined()
    expect(api.getProjectProgress).toHaveBeenCalledTimes(2)
    expect(api.completeProject).toHaveBeenCalledTimes(1)
  })

  it('姓名筛选正常查询，重置后恢复全部任务', async () => {
    await open(['feedback:progress:view'])
    await wrapper.find('input[placeholder="输入评价人姓名"]').setValue('张三')
    await wrapper.find('input[placeholder="输入被评价人姓名"]').setValue('李四')
    await button('查询').trigger('click')
    await flushPromises()
    expect(api.getProjectProgress).toHaveBeenLastCalledWith(12, {
      evaluatorKeyword: '张三', targetKeyword: '李四', pageNum: 1, pageSize: 20
    })
    await button('重置').trigger('click')
    await flushPromises()
    expect(api.getProjectProgress).toHaveBeenLastCalledWith(12, { pageNum: 1, pageSize: 20 })
  })
})
