import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import ElementPlus from 'element-plus'
import { expect, it, vi } from 'vitest'
import SubmittedAnswersView from '@/views/hr/SubmittedAnswersView.vue'
import { useAuthStore } from '@/stores/auth'
const api = vi.hoisted(() => ({ listAnswerProjects: vi.fn(), listSubmittedAnswers: vi.fn() }))
vi.mock('@/api/feedback/reports', () => api)
it('仅答卷权限按项目名称选择，入口不要求手填ID，项目链接解析名称', async () => {
  api.listAnswerProjects.mockResolvedValue({ rows: [{ projectId: 1, projectName: '年度评价', status: 'ACTIVE' }] })
  api.listSubmittedAnswers.mockResolvedValue({ rows: [{ assignmentId: 1, rawTotalScore: '0.0000' }, { assignmentId: 2, rawTotalScore: '82.5000' }, { assignmentId: 3, rawTotalScore: null }], total: 3 })
  const pinia = createPinia(); setActivePinia(pinia)
  useAuthStore().permissions = ['feedback:answer:view']
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/hr/answers', component: SubmittedAnswersView }, { path: '/hr/projects/:projectId/answers', component: SubmittedAnswersView }] })
  await router.push('/hr/answers')
  const wrapper = mount(SubmittedAnswersView, { global: { plugins: [pinia, router, ElementPlus] } })
  await flushPromises()
  expect(wrapper.text()).not.toContain('项目ID')
  expect(wrapper.text()).toContain('请先按名称选择评价项目')
  expect(api.listSubmittedAnswers).not.toHaveBeenCalled()
  await router.push('/hr/projects/1/answers'); await flushPromises()
  expect(api.listAnswerProjects).toHaveBeenCalledWith({ projectId: 1, pageNum: 1, pageSize: 1 })
  expect(wrapper.text()).toContain('年度评价')
  expect(wrapper.findAll('.answer-score').map(cell => cell.text())).toEqual(['0', '82.5', '暂无分数'])
  expect(wrapper.text()).not.toContain('查看项目报告')
  expect(api.listSubmittedAnswers).toHaveBeenCalledWith(1, expect.any(Object))
  wrapper.unmount()
})
