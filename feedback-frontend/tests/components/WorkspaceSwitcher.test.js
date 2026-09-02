import ElementPlus from 'element-plus'
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import WorkspaceSwitcher from '@/components/WorkspaceSwitcher.vue'

describe('WorkspaceSwitcher', () => {
  it('双权限用户可以从HR工作台切换到员工工作台', async () => {
    const employeeWorkspace = { key: 'employee', label: '员工工作台', path: '/employee/todos' }
    const wrapper = mount(WorkspaceSwitcher, {
      global: { plugins: [ElementPlus] },
      props: {
        currentWorkspace: 'hr',
        workspaces: [
          { key: 'hr', label: 'HR 工作台', path: '/hr/projects' },
          employeeWorkspace
        ]
      }
    })

    await wrapper.findAll('button')[1].trigger('click')

    expect(wrapper.emitted('switch')).toEqual([[employeeWorkspace]])
  })

  it('单工作台用户不显示多余切换入口', () => {
    const wrapper = mount(WorkspaceSwitcher, {
      global: { plugins: [ElementPlus] },
      props: {
        currentWorkspace: 'employee',
        workspaces: [{ key: 'employee', label: '员工工作台', path: '/employee/todos' }]
      }
    })

    expect(wrapper.text()).toBe('')
  })
})
