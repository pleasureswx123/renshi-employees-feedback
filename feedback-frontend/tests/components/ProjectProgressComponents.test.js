import ElementPlus from 'element-plus'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import CompletionPrecheckDrawer from '@/components/feedback/progress/CompletionPrecheckDrawer.vue'
import ProgressAssignmentList from '@/components/feedback/progress/ProgressAssignmentList.vue'
import ProgressKpiGrid from '@/components/feedback/progress/ProgressKpiGrid.vue'

const summary = {
  totalCount: 10,
  submittedCount: 6,
  draftCount: 2,
  pendingCount: 1,
  closedIncompleteCount: 1,
  incompleteCount: 4,
  completionRate: '60.00'
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
    impactMessages: [],
    precheckedAt: '2026-09-02T10:05:00',
    ...overrides
  }
}

describe('评价进度KPI', () => {
  it('渲染六张服务端KPI并通过点击发出精确状态筛选', async () => {
    const wrapper = mount(ProgressKpiGrid, {
      global: { plugins: [ElementPlus] },
      props: { summary, activeStatus: '' }
    })

    const cards = wrapper.findAll('button.kpi-card')
    expect(cards).toHaveLength(6)
    expect(wrapper.text()).toContain('应完成')
    expect(wrapper.text()).toContain('60.00%')
    await cards[2].trigger('click')
    expect(wrapper.emitted('filter')).toEqual([['DRAFT']])
    await cards[0].trigger('click')
    expect(wrapper.emitted('filter').at(-1)).toEqual([''])
  })
})

describe('回收明细响应式列表', () => {
  it('同一真实明细同时提供桌面表格和移动卡片且不渲染答案入口', () => {
    const rows = [{
      assignmentId: 101,
      evaluatorName: '张三',
      evaluatorDeptName: '研发部',
      targetName: '李四',
      targetDeptName: '产品部',
      relationName: '同级',
      status: 'DRAFT',
      savedTime: '2026-09-02T10:00:00',
      submittedTime: null,
      closedTime: null
    }]
    const wrapper = mount(ProgressAssignmentList, {
      global: { plugins: [ElementPlus] },
      props: { rows, loading: false }
    })
    expect(wrapper.find('.desktop-table').exists()).toBe(true)
    expect(wrapper.find('.mobile-cards').exists()).toBe(true)
    expect(wrapper.text()).toContain('张三')
    expect(wrapper.text()).toContain('李四')
    expect(wrapper.text()).not.toContain('查看答案')
    expect(wrapper.text()).not.toContain('导出')
  })

  it('关闭未完成任务优先展示关闭时间而非旧草稿保存时间', () => {
    const wrapper = mount(ProgressAssignmentList, {
      global: { plugins: [ElementPlus] },
      props: { rows: [{ assignmentId: 2, evaluatorName: '张三', targetName: '李四', relationName: '同级', status: 'CLOSED_INCOMPLETE', savedTime: '2026-09-01T09:00:00', closedTime: '2026-09-02T10:06:00' }] }
    })
    expect(wrapper.text()).toContain('2026-09-02 10:06:00')
    expect(wrapper.text()).not.toContain('2026-09-01 09:00:00')
  })
})

describe('完成项目预检抽屉', () => {
  afterEach(() => { document.body.innerHTML = '' })

  it('展示缺失关系和后端影响说明，Unicode原因校验通过且勾选后才提交', async () => {
    const precheck = completionPrecheck({
      missingRelations: [{ targetUserId: 21, targetName: '李四', relationId: 8, relationName: '同级', assignmentCount: 2, submittedCount: 0 }],
      impactMessages: ['完成后未提交任务将关闭。'],
      precheckedAt: '2026-09-02T10:05:00'
    })
    const wrapper = mount(CompletionPrecheckDrawer, {
      attachTo: document.body,
      global: { plugins: [ElementPlus] },
      props: { modelValue: true, precheck, completing: false }
    })
    await flushPromises()

    expect(document.body.textContent).toContain('李四')
    expect(document.body.textContent).toContain('完成后未提交任务将关闭。')
    expect(document.body.textContent).toContain('还有 3 份评价未提交')
    expect(document.body.textContent).toContain('报告仅使用 6 份已提交答卷')
    expect(document.body.textContent).toContain('项目结束后不能重新打开')
    expect([...document.body.querySelectorAll('button')].find(item => item.textContent.includes('确认提前结束')).disabled).toBe(true)
    const textarea = document.body.querySelector('textarea')
    textarea.value = '  😀本轮截止  '
    textarea.dispatchEvent(new Event('input'))
    const checkbox = document.body.querySelector('input[type="checkbox"]')
    checkbox.checked = true
    checkbox.dispatchEvent(new Event('change'))
    await flushPromises()
    const submit = [...document.body.querySelectorAll('button')].find(item => item.textContent.includes('确认提前结束'))
    submit.click()
    await flushPromises()

    expect(wrapper.emitted('submit')).toEqual([['😀本轮截止']])
  })

  it('空白或超过500个Unicode字符时不提交', async () => {
    const wrapper = mount(CompletionPrecheckDrawer, {
      attachTo: document.body,
      global: { plugins: [ElementPlus] },
      props: { modelValue: true, precheck: completionPrecheck(), completing: false }
    })
    await flushPromises()
    const textarea = document.body.querySelector('textarea')
    textarea.value = '😀'.repeat(501)
    textarea.dispatchEvent(new Event('input'))
    const checkbox = document.body.querySelector('input[type="checkbox"]')
    checkbox.checked = true
    checkbox.dispatchEvent(new Event('change'))
    await flushPromises()
    const submit = [...document.body.querySelectorAll('button')].find(item => item.textContent.includes('确认提前结束'))
    submit.click()
    await flushPromises()
    expect(wrapper.emitted('submit')).toBeUndefined()
    await vi.waitFor(() => expect(document.body.textContent).toContain('完成原因不能超过500个字符'))
  })
})
