import ElementPlus from 'element-plus'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import TargetSelectorPanel from '@/components/feedback/publication/TargetSelectorPanel.vue'

const person = { userId: 20, nickName: '张三', userName: 'zhang', deptName: '研发部', available: true }
let wrapper
afterEach(() => wrapper?.unmount())
function open(extra = {}) {
  const loadDepartments = vi.fn().mockResolvedValue([{ deptId: 2, parentId: 0, label: '研发部', directCount: 2 }])
  const loadPeople = vi.fn().mockResolvedValue({ rows: [person], total: 51 })
  wrapper = mount(TargetSelectorPanel, { global: { plugins: [ElementPlus] }, props: { editable: true, canBrowse: true, selectedTargets: [], loadDepartments, loadPeople, ...extra } })
  return { loadDepartments, loadPeople }
}
describe('组织树选人穿梭框', () => {
  it('整部门读取所有分页与下级部门，排除本人、失效和重复人员', async () => {
    const colleague = { ...person, userId: 21, nickName: '李四' }
    const child = { ...person, userId: 22, nickName: '王五' }
    const loadPeople = vi.fn().mockImplementation(async ({ deptId, pageNum }) => {
      if (deptId === 3) return { rows: [child, colleague], total: 2 }
      return pageNum === 1 ? { rows: [person, colleague, { ...person, userId: 99, available: false }], total: 51 } : { rows: [colleague], total: 51 }
    })
    open({ allowDepartment: true, excludedIds: [person.userId], loadPeople,
      loadDepartments: async () => [{ deptId: 2, parentId: 0, label: '研发部', directCount: 0 }, { deptId: 3, parentId: 2, label: '研发组', directCount: 0 }] })
    await flushPromises()
    await wrapper.get('[aria-label="添加研发部全部人员"]').trigger('click')
    await flushPromises()
    expect(loadPeople).toHaveBeenCalledWith({ deptId: 2, pageNum: 2, pageSize: 50 })
    expect(loadPeople).toHaveBeenCalledWith({ deptId: 3, pageNum: 1, pageSize: 50 })
    expect(wrapper.emitted('add')).toEqual([[colleague], [child]])
  })

  it('整部门后续页失败时不添加部分人员，允许重试', async () => {
    const loadPeople = vi.fn().mockResolvedValueOnce({ rows: [person], total: 51 }).mockRejectedValueOnce(new Error('读取失败'))
    open({ allowDepartment: true, loadPeople })
    await flushPromises()
    await wrapper.get('[aria-label="添加研发部全部人员"]').trigger('click')
    await flushPromises()
    expect(wrapper.emitted('add')).toBeUndefined()
    expect(wrapper.get('[role="alert"]').text()).toContain('读取失败')
    loadPeople.mockResolvedValue({ rows: [person], total: 1 })
    await wrapper.get('[aria-label="添加研发部全部人员"]').trigger('click')
    await flushPromises()
    expect(wrapper.emitted('add')).toEqual([[person]])
  })

  it('整部门加载期间重复点击不重复请求，卸载后忽略迟到结果', async () => {
    let finish
    const loadPeople = vi.fn(() => new Promise(resolve => { finish = resolve }))
    open({ allowDepartment: true, loadPeople })
    await flushPromises()
    await wrapper.get('[aria-label="添加研发部全部人员"]').trigger('click')
    await wrapper.get('[aria-label="添加研发部全部人员"]').trigger('click')
    expect(loadPeople).toHaveBeenCalledOnce()
    wrapper.unmount()
    finish({ rows: [person], total: 1 })
    await flushPromises()
    expect(wrapper.emitted('add')).toBeUndefined()
  })

  it('默认展开公司层级展示部门，部门人员仍按需加载', async () => {
    const loadDepartments = vi.fn().mockResolvedValue([
      { deptId: 1, parentId: 0, label: '总公司', directCount: 0 },
      { deptId: 2, parentId: 1, label: '分公司', directCount: 0 },
      { deptId: 3, parentId: 2, label: '研发部', directCount: 2 }
    ])
    const { loadPeople } = open({ loadDepartments })
    await flushPromises()
    await vi.waitFor(() => expect(wrapper.findAll('.department-node').map(node => node.text())).toEqual(['总公司', '分公司', '研发部']))
    const tree = wrapper.findComponent({ name: 'ElTree' })
    expect(tree.vm.getNode('dept-1').expanded).toBe(true)
    expect(tree.vm.getNode('dept-2').expanded).toBe(true)
    expect(tree.vm.getNode('dept-3').expanded).toBe(false)
    expect(loadPeople).not.toHaveBeenCalled()
  })
  it('展开部门才加载人员，加载更多保留勾选，批量添加只发送人员', async () => {
    const { loadPeople } = open()
    await flushPromises()
    expect(loadPeople).not.toHaveBeenCalled()
    await wrapper.get('.el-tree-node__expand-icon').trigger('click')
    await flushPromises()
    expect(loadPeople).toHaveBeenCalledWith({ deptId: 2, pageNum: 1, pageSize: 50 })
    const tree = wrapper.findComponent({ name: 'ElTree' })
    tree.vm.setCheckedKeys(['user-20'])
    tree.vm.$emit('check', tree.vm.getNode('user-20').data, { checkedKeys: ['user-20'], checkedNodes: tree.vm.getCheckedNodes(), halfCheckedKeys: [], halfCheckedNodes: [] })
    await flushPromises()
    await wrapper.get('[aria-label="添加选中人员"]').trigger('click')
    expect(wrapper.emitted('add')).toEqual([[person]])
    expect(wrapper.text()).toContain('加载更多')
  })

  it('加载下一批人员不会重复已有节点或清掉勾选，并支持批量移除', async () => {
    const other = { ...person, userId: 21, nickName: '李四' }
    const { loadPeople } = open({ selectedTargets: [other] })
    await flushPromises()
    await wrapper.get('.el-tree-node__expand-icon').trigger('click')
    await flushPromises()
    const tree = wrapper.findComponent({ name: 'ElTree' })
    tree.vm.setCheckedKeys(['user-20'])
    loadPeople.mockResolvedValueOnce({ rows: [person, other], total: 51 })
    await wrapper.get('.more-node').trigger('click')
    await flushPromises()
    expect(loadPeople).toHaveBeenLastCalledWith({ deptId: 2, pageNum: 2, pageSize: 50 })
    expect(tree.vm.getCheckedKeys()).toEqual(['user-20'])
    expect(wrapper.findAll('.person-node')).toHaveLength(2)
    const table = wrapper.findComponent({ name: 'ElTable' })
    table.vm.$emit('selection-change', [other])
    await flushPromises()
    await wrapper.get('[aria-label="移除选中人员"]').trigger('click')
    expect(wrapper.emitted('remove')).toEqual([[21]])
  })

  it('搜索切换后忽略迟到的部门人员响应，回车不会提交表单或重复请求', async () => {
    const { loadPeople } = open()
    await flushPromises()
    let finish
    loadPeople.mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
    await wrapper.get('.el-tree-node__expand-icon').trigger('click')
    await wrapper.get('.participant-filter input').setValue(' 李四 ')
    loadPeople.mockResolvedValueOnce({ rows: [{ ...person, userId: 21, nickName: '李四' }], total: 1 })
    const input = wrapper.get('.participant-filter input')
    const enter = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true })
    input.element.dispatchEvent(enter)
    expect(enter.defaultPrevented).toBe(true)
    await input.trigger('keydown', { key: 'Enter', repeat: true })
    await input.trigger('keydown', { key: 'Enter', isComposing: true })
    await flushPromises()
    expect(loadPeople).toHaveBeenCalledTimes(2)
    finish({ rows: [person], total: 1 })
    await flushPromises()
    expect(wrapper.findComponent({ name: 'ElTree' }).vm.getNode('user-20')).toBeNull()
    expect(wrapper.get('.person-node').text()).toContain('李四')
  })
  it('搜索保留已选名单、过滤已选人员，搜索失败可重试', async () => {
    const { loadPeople } = open({ selectedTargets: [person] })
    await flushPromises()
    loadPeople.mockRejectedValueOnce(new Error('查询失败'))
    await wrapper.get('.participant-filter input').setValue('张')
    await wrapper.get('.participant-filter button').trigger('click')
    await flushPromises()
    expect(wrapper.get('.selected-column').text()).toContain('张三')
    expect(wrapper.text()).toContain('查询失败')
    await wrapper.get('.participant-filter button').trigger('click')
    await flushPromises()
    expect(wrapper.findComponent({ name: 'ElTree' }).vm.getNode('user-20').disabled).toBe(true)
  })
  it('无选人权限不加载组织与员工，保留已选只读名单', async () => {
    const { loadDepartments, loadPeople } = open({ canBrowse: false, editable: false, selectedTargets: [person] })
    await flushPromises()
    expect(loadDepartments).not.toHaveBeenCalled()
    expect(loadPeople).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('张三')
    expect(wrapper.find('[aria-label="添加选中人员"]').exists()).toBe(false)
  })
})
