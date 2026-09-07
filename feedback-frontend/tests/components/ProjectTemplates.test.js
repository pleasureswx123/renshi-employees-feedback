import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import ElementPlus, { ElSelect, ElInput, ElDialog } from 'element-plus'
import { expect, it, vi } from 'vitest'
import ProjectListView from '@/views/hr/ProjectListView.vue'
import { useAuthStore } from '@/stores/auth'
const api = vi.hoisted(() => ({ listProjects: vi.fn(), listSystemTemplates: vi.fn(), createProject: vi.fn(), removeProject: vi.fn(), updateProject: vi.fn() }))
vi.mock('@/api/feedback/projects', () => api)
it.each(['employee-360-v1', ''])('创建项目保留问卷来源选择：%s', async (templateKey) => {
  api.listProjects.mockResolvedValue({ rows: [], total: 0 })
  api.listSystemTemplates.mockResolvedValue({ data: [{ templateKey: 'employee-360-v1', name: '员工综合评价', description: '模板说明', scale: ['很少体现'], indicators: [{ name: '团队合作', weight: 100, questions: ['协助同事'] }] }] })
  api.createProject.mockResolvedValue({ data: { projectId: 9 } })
  const pinia = createPinia(); setActivePinia(pinia)
  useAuthStore().permissions = ['feedback:project:add']
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/hr/projects', component: ProjectListView }, { path: '/hr/projects/:id/editor', component: { template: '<div />' } }] })
  await router.push('/hr/projects')
  const wrapper = mount(ProjectListView, { global: { plugins: [pinia, router, ElementPlus] } })
  await flushPromises()
  await wrapper.findAll('button').find(b => b.text().includes('创建项目')).trigger('click')
  await flushPromises()
  const dialog = wrapper.findComponent(ElDialog)
  dialog.findAllComponents(ElInput)[0].vm.$emit('update:modelValue', '模板创建测试')
  dialog.findComponent(ElSelect).vm.$emit('update:modelValue', templateKey)
  await flushPromises()
  if (templateKey) expect(dialog.find('.template-preview').text()).toContain('团队合作')
  await dialog.findAll('button').find(b => b.text().includes('创建并编辑问卷')).trigger('click')
  await flushPromises()
  expect(api.createProject).toHaveBeenLastCalledWith({ projectName: '模板创建测试', description: null, questionnaireTitle: '模板创建测试', ...(templateKey ? { templateKey } : {}) })
  expect(router.currentRoute.value.path).toBe('/hr/projects/9/editor')
  wrapper.unmount()
})
