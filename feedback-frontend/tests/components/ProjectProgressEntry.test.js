import ElementPlus from 'element-plus'
import { createMemoryHistory, createRouter } from 'vue-router'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import ProjectProgressEntryView from '@/views/hr/ProjectProgressEntryView.vue'

let wrapper

async function mountEntry() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/hr/progress', component: ProjectProgressEntryView },
      { path: '/hr/projects/:projectId/progress', component: { template: '<div>项目进度</div>' } }
    ]
  })
  await router.push('/hr/progress')
  wrapper = mount(ProjectProgressEntryView, { global: { plugins: [router, ElementPlus] } })
  await flushPromises()
  return router
}

describe('回收进度安全入口', () => {
  afterEach(() => wrapper?.unmount())

  it('使用ElForm正整数规则并通过明确按钮进入项目进度页', async () => {
    const router = await mountEntry()
    const input = wrapper.findComponent({ name: 'ElInputNumber' })
    expect(input.props('stepStrictly')).toBe(true)
    expect(wrapper.findComponent({ name: 'ElForm' }).exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'ElFormItem' }).props('prop')).toBe('projectId')

    await input.vm.$emit('update:modelValue', 12)
    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/hr/projects/12/progress')
  })

  it('小数项目ID不跳转并显示正整数校验反馈', async () => {
    const router = await mountEntry()
    const form = wrapper.findComponent({ name: 'ElForm' })
    const validator = form.props('rules').projectId[0].validator
    let validationError
    validator({}, 1.5, error => { validationError = error })

    expect(router.currentRoute.value.path).toBe('/hr/progress')
    expect(validationError?.message).toBe('项目ID必须为正整数')
  })
})
