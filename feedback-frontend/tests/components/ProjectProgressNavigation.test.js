import ElementPlus from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, RouterView } from 'vue-router'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import WorkspaceLayout from '@/layouts/WorkspaceLayout.vue'
import ProjectListView from '@/views/hr/ProjectListView.vue'
import { useAuthStore } from '@/stores/auth'

const api = vi.hoisted(() => ({
  createProject: vi.fn(),
  listProjects: vi.fn(),
  removeProject: vi.fn(),
  updateProject: vi.fn()
}))
vi.mock('@/api/feedback/projects', () => api)

let wrapper
let pinia

describe('项目列表进度入口与子路由菜单', () => {
  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    useAuthStore().permissions = ['feedback:project:list', 'feedback:progress:view']
    api.listProjects.mockResolvedValue({
      rows: [
        { projectId: 1, projectName: '准备项目', status: 'PREPARING', lockVersion: 1 },
        { projectId: 2, projectName: '进行项目', status: 'ACTIVE', lockVersion: 1 },
        { projectId: 3, projectName: '完成项目', status: 'COMPLETED', lockVersion: 2 }
      ],
      total: 3
    })
  })
  afterEach(() => { wrapper?.unmount(); document.body.innerHTML = '' })

  it('仅ACTIVE和COMPLETED项目显示回收进度入口并进入固定路由', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/hr/projects', component: ProjectListView },
        { path: '/hr/projects/:projectId/progress', component: { template: '<div>进度页</div>' } }
      ]
    })
    await router.push('/hr/projects')
    wrapper = mount(RouterView, { global: { plugins: [pinia, router, ElementPlus] } })
    await flushPromises()

    const progressButtons = wrapper.findAll('button').filter(item => item.text() === '回收进度')
    expect(progressButtons).toHaveLength(2)
    await progressButtons[0].trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/hr/projects/2/progress')
  })

  it('进度子路由使用activeMenu持续高亮评价项目', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{
        path: '/hr',
        component: WorkspaceLayout,
        props: { workspace: 'hr', title: 'HR工作台' },
        children: [{
          path: 'projects/:projectId/progress',
          component: { template: '<div>进度页</div>' },
          meta: { activeMenu: '/hr/projects' }
        }]
      }]
    })
    await router.push('/hr/projects/2/progress')
    wrapper = mount(RouterView, { global: { plugins: [pinia, router, ElementPlus] } })
    await flushPromises()
    const menus = wrapper.findAllComponents({ name: 'ElMenu' })
    expect(menus).toHaveLength(1)
    expect(menus.every(menu => menu.props('defaultActive') === '/hr/projects')).toBe(true)
  })

  it('收起侧栏保留权限菜单，移动抽屉选择后关闭并更新面包屑', async () => {
    useAuthStore().permissions = ['feedback:project:list', 'feedback:report:view']
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{
        path: '/hr', component: WorkspaceLayout, props: { workspace: 'hr', title: 'HR 工作台' },
        children: [
          { path: 'projects', component: { template: '<div>项目列表</div>' }, meta: { title: '评价项目' } },
          { path: 'reports', component: { template: '<div>报告列表</div>' }, meta: { title: '评价报告' } }
        ]
      }]
    })
    await router.push('/hr/projects')
    wrapper = mount(RouterView, { attachTo: document.body, global: { plugins: [pinia, router, ElementPlus] } })
    await flushPromises()
    await wrapper.get('[aria-label="收起侧栏"]').trigger('click')
    expect(wrapper.findComponent({ name: 'ElMenu' }).props('collapse')).toBe(true)
    expect(router.currentRoute.value.path).toBe('/hr/projects')
    await wrapper.get('[aria-label="打开工作台导航"]').trigger('click')
    await flushPromises()
    expect(wrapper.findComponent({ name: 'ElDrawer' }).props('modelValue')).toBe(true)
    const navigation = wrapper.findAllComponents({ name: 'ElMenu' })[1]
    expect(navigation.text()).not.toContain('原始答案')
    await navigation.findAll('[role="menuitem"]')[1].trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/hr/reports')
    expect(wrapper.findComponent({ name: 'ElDrawer' }).props('modelValue')).toBe(false)
    expect(wrapper.get('.workspace-breadcrumb').text()).toContain('评价报告')
  })

  it('progress-only用户显示安全回收进度菜单并在明细页保持高亮', async () => {
    useAuthStore().permissions = ['feedback:progress:view']
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{
        path: '/hr',
        component: WorkspaceLayout,
        props: { workspace: 'hr', title: 'HR工作台' },
        children: [
          { path: 'progress', component: { template: '<div>进度入口</div>' } },
          {
            path: 'projects/:projectId/progress',
            component: { template: '<div>进度页</div>' },
            meta: { activeMenu: '/hr/projects' }
          }
        ]
      }]
    })
    await router.push('/hr/projects/2/progress')
    wrapper = mount(RouterView, { global: { plugins: [pinia, router, ElementPlus] } })
    await flushPromises()

    expect(wrapper.text()).toContain('回收进度')
    const menus = wrapper.findAllComponents({ name: 'ElMenu' })
    expect(menus.every(menu => menu.props('defaultActive') === '/hr/progress')).toBe(true)
  })
})
