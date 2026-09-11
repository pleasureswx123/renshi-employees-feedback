import ElementPlus, { ElMessageBox } from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { DOMWrapper, mount, flushPromises } from '@vue/test-utils'
import { beforeEach, afterEach, it, expect, vi } from 'vitest'
import ProjectListView from '@/views/hr/ProjectListView.vue'
import { useAuthStore } from '@/stores/auth'
const api = vi.hoisted(() => ({ listProjects: vi.fn(), getPublicationConfig: vi.fn(), publishProject: vi.fn(), savePublicationConfig: vi.fn() }))
vi.mock('@/api/feedback/projects', () => api)
let wrapper, router
beforeEach(async () => {
  vi.clearAllMocks()
  const pinia = createPinia(); setActivePinia(pinia)
  useAuthStore().permissions = ['feedback:project:publish']
  api.listProjects.mockResolvedValue({ rows: [{ projectId: 7, projectName: '测试项目', status: 'PREPARING' }], total: 1 })
  api.getPublicationConfig.mockResolvedValue({ data: { editable: true, isPublishReady: true, validationIssues: [], preview: { targetCount: 2, assignmentCount: 8 }, projectLockVersion: 3, versionId: 4, versionLockVersion: 5 } })
  api.publishProject.mockResolvedValue({ data: {} })
  router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/hr/projects', component: ProjectListView }, { path: '/hr/projects/:id/editor', component: { template: '<div />' } }] })
  await router.push('/hr/projects')
  wrapper = mount(ProjectListView, { global: { plugins: [pinia, router, ElementPlus] } })
  await flushPromises()
})
afterEach(() => { wrapper.unmount(); vi.restoreAllMocks() })
async function publish() { await wrapper.findAll('button').find(item => item.text() === '发布项目').trigger('click'); await flushPromises() }
it('发布重新检查，确认后使用最新版本锁并刷新列表', async () => {
  vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm')
  await publish()
  expect(api.getPublicationConfig).toHaveBeenCalledWith(7)
  expect(api.publishProject).toHaveBeenCalledWith(7, { projectLockVersion: 3, versionId: 4, versionLockVersion: 5 })
  expect(api.listProjects).toHaveBeenCalledTimes(2)
})
it('取消确认不发布，校验失败可返回配置', async () => {
  const confirm = vi.spyOn(ElMessageBox, 'confirm').mockRejectedValue('cancel')
  await publish()
  expect(api.publishProject).not.toHaveBeenCalled()
  api.getPublicationConfig.mockResolvedValue({ data: { editable: true, isPublishReady: false, validationIssues: [{ message: '缺少上级评价人' }] } })
  confirm.mockResolvedValue('confirm')
  await publish()
  expect(api.publishProject).not.toHaveBeenCalled()
  expect(router.currentRoute.value.fullPath).toBe('/hr/projects/7/editor?step=6')
})
it('无发布权限不显示操作', async () => {
  useAuthStore().permissions = ['feedback:participant:manage']
  await flushPromises()
  expect(wrapper.findAll('button').some(item => item.text() === '发布项目')).toBe(false)
})

it('预览未完成配置展示四个只读页签和缺项，不保存或发布，失败可重试', async () => {
  api.getPublicationConfig.mockResolvedValue({ data: { projectId: 7, editable: true, isPublishReady: false, validationIssues: [{ message: '缺少上级评价人' }] } })
  const previewButton = () => wrapper.findAll('button').find(item => item.text() === '预览项目')
  await previewButton().trigger('click')
  await flushPromises()
  const body = new DOMWrapper(document.body)
  expect(body.get('.el-drawer__footer').text()).toContain('缺少上级评价人')
  expect(body.get('.el-drawer__footer').text()).toContain('待完善 1 项')
  expect(body.findAll('.el-drawer [role="tab"]').map(tab => tab.text())).toEqual(['问卷预览', '指标与权重及绑定题目', '评价关系与计分占比', '被评价人与评价人安排'])
  expect(body.get('.el-drawer').text()).not.toContain('返回修改')
  expect(api.savePublicationConfig).not.toHaveBeenCalled()
  expect(api.publishProject).not.toHaveBeenCalled()
  await body.findAll('.el-drawer button').find(button => button.text() === '关闭').trigger('click')
  await flushPromises()
  api.getPublicationConfig.mockRejectedValueOnce(new Error('网络异常'))
  await previewButton().trigger('click')
  await flushPromises()
  expect(body.get('.el-drawer').text()).toContain('网络异常')
  await body.findAll('.el-drawer button').find(button => button.text() === '重新加载').trigger('click')
  await flushPromises()
  expect(body.get('.el-drawer__footer').text()).toContain('缺少上级评价人')
  expect(body.get('.el-drawer__footer').text()).toContain('待完善 1 项')
})

it('完整配置底部显示可发布状态，不出现待完善操作', async () => {
  await wrapper.findAll('button').find(item => item.text() === '预览项目').trigger('click')
  await flushPromises()
  const footer = new DOMWrapper(document.body).get('.el-drawer__footer')
  expect(footer.text()).toContain('配置完整，可以发布')
  expect(footer.text()).not.toContain('去完善配置')
})
