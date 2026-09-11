import ElementPlus, { ElMessageBox } from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, RouterView } from 'vue-router'
import { DOMWrapper, flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

import PublicationPreviewPanel from '@/components/feedback/publication/PublicationPreviewPanel.vue'
import RelationConfigPanel from '@/components/feedback/publication/RelationConfigPanel.vue'
import EvaluatorSelectionPanel from '@/components/feedback/publication/EvaluatorSelectionPanel.vue'
import PublicationConfigView from '@/views/hr/PublicationConfigView.vue'
import { useAuthStore } from '@/stores/auth'
import { usePublicationConfigStore } from '@/stores/publicationConfig'

const api = vi.hoisted(() => ({ getParticipantDepartments: vi.fn().mockResolvedValue({ data: [] }), getPublicationConfig: vi.fn(), listParticipantOptions: vi.fn(), publishProject: vi.fn(), savePublicationConfig: vi.fn() }))
vi.mock('@/api/feedback/projects', () => api)

const preview = {
  targetCount: 1,
  evaluatorCount: 2,
  assignmentCount: 2,
  targetSummaries: [{ targetUserId: 10, selfCount: 1, nonSelfCount: 1, assignmentCount: 2 }]
}

const relations = [
  {
    relationId: 1,
    relationCode: 'REL_PEER',
    relationType: 'PEER',
    relationName: '同级',
    isEnabled: true,
    participatesInScore: true,
    weight: '100.0000',
    sortOrder: 1,
    fixed: true
  },
  {
    relationId: 2,
    relationCode: 'REL_SELF',
    relationType: 'SELF',
    relationName: '自己',
    isEnabled: true,
    participatesInScore: false,
    weight: '0.0000',
    sortOrder: 2,
    fixed: true
  }
]

describe('P5发布配置组件', () => {
  it('评价人通过组织树搜索，回车只发送一次查询', async () => {
    const loadPeople = vi.fn().mockResolvedValue({ rows: [], total: 0 })
    const wrapper = mount(EvaluatorSelectionPanel, {
      global: { plugins: [ElementPlus], stubs: { teleport: false } },
      props: { editable: true, targets: [{ userId: 10, nickName: '张三' }], relations,
        loadDepartments: async () => [], loadPeople }
    })
    await flushPromises()
    expect(wrapper.find('.participant-filter input').exists()).toBe(false)
    wrapper.vm.locate({ targetUserId: 10 })
    await flushPromises()
    expect(new DOMWrapper(document.body).get('[role="dialog"]').text()).toContain('配置评价人 · 张三')
    const input = new DOMWrapper(document.body).get('.participant-filter input')
    await input.setValue(' 李四 ')
    await input.trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(loadPeople).toHaveBeenCalledOnce()
    expect(loadPeople).toHaveBeenCalledWith({ pageNum: 1, pageSize: 50, keyword: '李四' })
    await input.trigger('keydown', { key: 'Enter', repeat: true })
    await input.trigger('keydown', { key: 'Enter', isComposing: true })
    expect(loadPeople).toHaveBeenCalledOnce()
    wrapper.unmount()
  })

  it('同级整部门批量添加不丢人，切换上级后不提供整部门入口', async () => {
    const people = [{ userId: 11, nickName: '甲', available: true }, { userId: 12, nickName: '乙', available: true }]
    const wrapper = mount(EvaluatorSelectionPanel, {
      global: { plugins: [ElementPlus], stubs: { teleport: false } }, props: {
        editable: true, targets: [{ userId: 10, nickName: '张三' }],
        relations: [...relations, { ...relations[0], relationCode: 'REL_UPPER', relationType: 'SUPERVISOR', relationName: '上级' }],
        loadDepartments: async () => [{ deptId: 2, parentId: 0, label: '研发部', directCount: 0 }],
        loadPeople: async () => ({ rows: people, total: 2 })
      }
    })
    await flushPromises()
    wrapper.vm.locate({ targetUserId: 10 })
    await flushPromises()
    await new DOMWrapper(document.body).get('[aria-label="添加研发部全部人员"]').trigger('click')
    await flushPromises()
    expect(wrapper.emitted('set-evaluators').at(-1)).toEqual([10, 'REL_PEER', [11, 12]])
    expect(wrapper.emitted('remember-person')).toEqual(people.map(person => [person]))
    await new DOMWrapper(document.body).get('.relation-picker input[value="REL_UPPER"]').setValue(true)
    await flushPromises()
    expect(new DOMWrapper(document.body).find('[aria-label="添加研发部全部人员"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('展示后端权威预览数量和稳定问题定位', () => {
    const wrapper = mount(PublicationPreviewPanel, {
      global: { plugins: [ElementPlus], stubs: { teleport: false } },
      props: {
        preview,
        ready: false,
        issues: [
          { code: 'EVALUATOR_REQUIRED', path: 'evaluatorSelections', message: '请为同级关系选择评价人' }
        ]
      }
    })

    expect(wrapper.text()).toContain('待处理 1 项')
    expect(wrapper.findAllComponents({ name: 'ElTable' }).at(-1).props('data')).toEqual([
      { code: 'EVALUATOR_REQUIRED', path: 'evaluatorSelections', message: '请为同级关系选择评价人' }
    ])
    expect(wrapper.text()).toContain('2')
  })

  it('只读评价安排仍可切换查看，显示失效人员且不提供移除入口', async () => {
    const target = { userId: 10, nickName: '张三' }
    const upper = { ...relations[0], relationCode: 'REL_UPPER', relationName: '上级' }
    const wrapper = mount(EvaluatorSelectionPanel, {
      global: { plugins: [ElementPlus], stubs: { teleport: false } },
      props: {
        editable: false, loadDepartments: async () => [], loadPeople: async () => ({ rows: [], total: 0 }),
        targets: [target], summaries: [{ ...target, hasOthers: true }], relations: [upper, ...relations],
        selections: [{ targetUserId: 10, relationCode: 'REL_PEER', evaluatorUserIds: [11, 12] }],
        participants: [{ userId: 11, userName: '同事账号', available: true }, { userId: 12, nickName: '离职同事', available: false }]
      }
    })
    await flushPromises()
    expect(wrapper.get('.assignment-summary').text()).toContain('离职同事（失效）')
    await wrapper.get('button[aria-label="查看张三的同级评价人"]').trigger('click')
    await flushPromises()
    expect(new DOMWrapper(document.body).get('.selected-column').text()).toContain('已选同级评价人（2）')
    expect(wrapper.findAll('button').some(button => button.text() === '移除')).toBe(false)
    expect(wrapper.emitted('set-evaluators')).toBeUndefined()
    wrapper.unmount()
  })

  it('冻结视图禁用关系编辑且不显示增删入口', () => {
    const wrapper = mount(RelationConfigPanel, {
      global: { plugins: [ElementPlus], stubs: { teleport: false } },
      props: { relations, editable: false }
    })

    expect(wrapper.text()).not.toContain('增加自定义关系')
    expect(wrapper.text()).not.toContain('删除')
    expect(wrapper.findAll('input').every(input => input.attributes('disabled') !== undefined)).toBe(true)
  })

  it('计分摘要跟随名称、占比和计分状态变化，并排除自评和停用关系', async () => {
    const upper = { ...relations[0], relationCode: 'REL_SUPERVISOR', relationName: '上级', weight: '60.0000' }
    const peer = { ...relations[0], weight: '40.0000' }
    const other = { ...relations[0], relationCode: 'REL_OTHER', relationName: '其他', isEnabled: false, weight: '80.0000' }
    const wrapper = mount(RelationConfigPanel, {
      global: { plugins: [ElementPlus], stubs: { teleport: false } },
      props: { relations: [upper, peer, relations[1], other], editable: true }
    })
    await flushPromises()
    const summary = () => wrapper.get('.scoring-summary')
    expect(summary().text()).toContain('上级占 60%，同级占 40%')
    expect(summary().text()).toContain('权重合计 100%')
    expect(summary().text()).toContain('占比已达标')
    expect(summary().text()).not.toContain('自己占')
    expect(summary().text()).not.toContain('其他占')
    expect(wrapper.find('input[aria-label="自己权重（%）"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('单独展示')

    await wrapper.setProps({ relations: [upper, { ...peer, relationName: '协作同事', weight: '60.0000' }] })
    expect(summary().text()).toContain('协作同事占 60%')
    expect(summary().text()).toContain('已超出 20%，请减少占比')
    expect(summary().getComponent({ name: 'ElAlert' }).props('type')).toBe('error')
    await wrapper.setProps({ relations: [upper, { ...peer, participatesInScore: false }] })
    expect(summary().text()).toContain('仅供参考：同级，不计入总分')
    expect(summary().text()).toContain('还差 40%，请补足占比')
    await wrapper.setProps({ relations: [relations[1]] })
    expect(summary().text()).toContain('尚未设置计分关系')
    expect(summary().text()).not.toContain('占比已达标')
    wrapper.unmount()
  })

  it('历史小数定点累加达标；零占比和无效输入不误报达标', async () => {
    const config = [
      { ...relations[0], weight: '33.3333' },
      { ...relations[0], relationCode: 'REL_OTHER', weight: '66.6667' }
    ]
    const wrapper = mount(RelationConfigPanel, { global: { plugins: [ElementPlus], stubs: { teleport: false } }, props: { relations: config } })
    expect(wrapper.get('.scoring-summary').text()).toContain('权重合计 100%')
    expect(wrapper.get('.scoring-summary').text()).toContain('占比已达标')
    expect(wrapper.emitted('update')).toBeUndefined()
    await wrapper.setProps({ relations: [{ ...config[0], weight: '0' }, { ...config[1], weight: '100' }] })
    expect(wrapper.get('.scoring-summary').text()).toContain('计入总分的关系占比须大于 0%')
    expect(wrapper.get('.scoring-summary').text()).not.toContain('占比已达标')
    await wrapper.setProps({ relations: [{ ...config[0], weight: 'invalid' }] })
    expect(wrapper.get('.scoring-summary').text()).toContain('请填写有效的占比')
    wrapper.unmount()
  })

  it('关系启用和发布冻结后，权重输入的无障碍禁用状态与实际状态一致', async () => {
    const wrapper = mount(RelationConfigPanel, {
      global: { plugins: [ElementPlus], stubs: { teleport: false } },
      props: { relations: [{ ...relations[0], participatesInScore: false }], editable: true }
    })
    await flushPromises()
    const input = () => wrapper.find('input[aria-label="同级权重（%）"]')
    expect(input().attributes('aria-disabled')).toBe('true')
    await wrapper.setProps({ relations: [{ ...relations[0], weight: '60.0000' }] })
    expect(input().attributes('disabled')).toBeUndefined()
    expect(input().attributes('aria-disabled')).toBe('false')
    expect(input().element.value).toBe('60')
    await wrapper.setProps({ editable: false })
    expect(input().attributes('disabled')).toBeDefined()
    expect(input().attributes('aria-disabled')).toBe('true')
    expect(input().element.value).toBe('60')
    wrapper.unmount()
  })
})

describe('人员配置返回问卷编辑', () => {
  let wrapper
  let router
  let store
  async function open({ editable = true, canEdit = true } = {}) {
    vi.clearAllMocks()
    const pinia = createPinia()
    setActivePinia(pinia)
    useAuthStore().permissions = ['feedback:participant:manage', ...(canEdit ? ['feedback:questionnaire:edit'] : [])]
    api.getPublicationConfig.mockResolvedValue({ data: { projectId: 7, projectName: '返回流程测试', editable } })
    api.listParticipantOptions.mockResolvedValue({ rows: [], total: 0 })
    router = createRouter({ history: createMemoryHistory(), routes: [
      { path: '/hr/projects/:projectId/publication', component: PublicationConfigView },
      { path: '/hr/projects/:projectId/editor', component: { template: '<div>问卷编辑器</div>' } },
      { path: '/hr/projects', component: { template: '<div>项目列表</div>' } }
    ] })
    await router.push('/hr/projects/7/publication')
    wrapper = mount(RouterView, { global: { plugins: [pinia, router, ElementPlus] } })
    await flushPromises()
    store = usePublicationConfigStore()
  }
  afterEach(() => { wrapper?.unmount(); vi.restoreAllMocks() })

  it('直接打开准备期配置也能返回当前项目问卷，无需依赖浏览器历史', async () => {
    await open()
    await wrapper.get('button[aria-label="返回问卷编辑"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/hr/projects/7/editor')
    expect(api.savePublicationConfig).not.toHaveBeenCalled()
  })

  it('取消离开保留未保存配置，确认离开后才返回问卷', async () => {
    await open()
    store.addTarget({ userId: 11, userName: '测试用户' })
    const confirm = vi.spyOn(ElMessageBox, 'confirm').mockRejectedValueOnce('cancel').mockResolvedValueOnce('confirm')
    await wrapper.get('button[aria-label="返回问卷编辑"]').trigger('click')
    await flushPromises()
    expect(confirm).toHaveBeenCalledWith('当前发布配置有未保存修改，确认离开吗？', '离开配置页', expect.any(Object))
    expect(router.currentRoute.value.path).toBe('/hr/projects/7/publication')
    expect(store.config.targets.map(target => target.userId)).toEqual([11])
    expect(store.dirty).toBe(true)
    await wrapper.get('button[aria-label="返回问卷编辑"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/hr/projects/7/editor')
    expect(api.savePublicationConfig).not.toHaveBeenCalled()
  })

  it.each([{ editable: false, canEdit: true }, { editable: true, canEdit: false }])('冻结或无问卷编辑权限时返回项目列表：%j', async options => {
    await open(options)
    expect(wrapper.find('button[aria-label="返回问卷编辑"]').exists()).toBe(false)
    await wrapper.get('button[aria-label="返回项目列表"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/hr/projects')
  })

  it.each(['saving', 'publishing'])('%s期间禁用返回入口', async state => {
    await open()
    store[state] = true
    await flushPromises()
    const back = wrapper.get('button[aria-label="返回问卷编辑"]')
    expect(back.element.disabled).toBe(true)
    await back.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/hr/projects/7/publication')
  })
})
