import ElementPlus, { ElMessage } from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, RouterView } from 'vue-router'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import ProjectListView from '@/views/hr/ProjectListView.vue'
import { useAuthStore } from '@/stores/auth'

const api = vi.hoisted(() => ({
  createProject: vi.fn(), listProjects: vi.fn(), removeProject: vi.fn(), updateProject: vi.fn()
}))
vi.mock('@/api/feedback/projects', () => api)

let wrapper
let router
let errors

function button(name) {
  return wrapper.findAllComponents({ name: 'ElButton' }).find(item => item.text() === name)
}

async function openProjectForm() {
  await button('创建项目').trigger('click')
  await flushPromises()
}

async function fillName() {
  await wrapper.findComponent({ name: 'ElDialog' }).find('input').setValue('浏览器走查回归项目')
}

describe('项目表单真实校验与提交保护', () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    const pinia = createPinia()
    setActivePinia(pinia)
    useAuthStore().permissions = ['feedback:project:list', 'feedback:project:add']
    api.listProjects.mockResolvedValue({ rows: [], total: 0 })
    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/hr/projects', component: ProjectListView },
        { path: '/hr/projects/:projectId/editor', component: { template: '<div>编辑器</div>' } }
      ]
    })
    await router.push('/hr/projects')
    errors = vi.fn()
    wrapper = mount(RouterView, {
      attachTo: document.body,
      global: { plugins: [pinia, router, ElementPlus], config: { errorHandler: error => errors(String(error)) } }
    })
    await flushPromises()
    await openProjectForm()
  })

  afterEach(() => { wrapper?.unmount(); ElMessage.closeAll(); document.body.innerHTML = '' })

  it('空名称只显示字段错误，不发送请求或产生未处理异常，随后仍可正常创建', async () => {
    await button('创建并编辑问卷').trigger('click')
    await flushPromises()
    await vi.waitFor(() => expect(document.body.textContent).toContain('请填写项目名称'))
    expect(api.createProject).not.toHaveBeenCalled()
    expect(errors).not.toHaveBeenCalled()
    expect(button('创建并编辑问卷').props('loading')).toBe(false)

    api.createProject.mockResolvedValue({ data: { projectId: 90 } })
    await fillName()
    await button('创建并编辑问卷').trigger('click')
    await flushPromises()
    expect(api.createProject).toHaveBeenCalledTimes(1)
    expect(router.currentRoute.value.path).toBe('/hr/projects/90/editor')
  })

  it('校验开始即阻止点击与回车重复提交，请求期间不能关闭或修改表单', async () => {
    let resolveRequest
    api.createProject.mockImplementation(() => new Promise(resolve => { resolveRequest = resolve }))
    await fillName()
    const submit = button('创建并编辑问卷')
    submit.vm.$emit('click', new MouseEvent('click'))
    submit.vm.$emit('click', new MouseEvent('click'))
    await wrapper.findComponent({ name: 'ElDialog' }).find('input').trigger('keyup', { key: 'Enter' })
    await flushPromises()
    expect(api.createProject).toHaveBeenCalledTimes(1)
    const dialog = wrapper.findComponent({ name: 'ElDialog' })
    expect(dialog.props('showClose')).toBe(false)
    expect(dialog.props('closeOnClickModal')).toBe(false)
    expect(dialog.props('closeOnPressEscape')).toBe(false)
    expect(dialog.find('input').attributes('disabled')).toBeDefined()

    resolveRequest({ data: { projectId: 91 } })
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/hr/projects/91/editor')
    expect(errors).not.toHaveBeenCalled()
  })

  it('接口失败保留表单并解除提交锁，不把失败抛给Vue事件处理器', async () => {
    api.createProject.mockRejectedValue(Object.assign(new Error('服务暂不可用'), { status: 503, __requestClassified: true }))
    await fillName()
    await button('创建并编辑问卷').trigger('click')
    await flushPromises()
    expect(wrapper.findComponent({ name: 'ElDialog' }).props('modelValue')).toBe(true)
    expect(button('创建并编辑问卷').props('loading')).toBe(false)
    expect(errors).not.toHaveBeenCalled()
    expect(router.currentRoute.value.path).toBe('/hr/projects')
  })

  it('项目说明中的回车只换行，不触发项目创建', async () => {
    await fillName()
    const description = wrapper.findComponent({ name: 'ElDialog' }).find('textarea')
    await description.setValue('第一行\n第二行')
    await description.trigger('keyup', { key: 'Enter' })
    await flushPromises()
    expect(api.createProject).not.toHaveBeenCalled()
    expect(description.element.value).toBe('第一行\n第二行')
  })
})
