import ElementPlus, { ElMessageBox } from 'element-plus'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, RouterView } from 'vue-router'
import { DOMWrapper, flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import PublicationConfigView from '@/views/hr/PublicationConfigView.vue'
import { useAuthStore } from '@/stores/auth'
import { usePublicationConfigStore } from '@/stores/publicationConfig'
import { analyzePublicationWorkflow, publicationIssueDestination } from '@/utils/publicationWorkflow'

const api = vi.hoisted(() => ({ getParticipantDepartments: vi.fn().mockResolvedValue({ data: [] }), getPublicationConfig: vi.fn(), listParticipantOptions: vi.fn(), savePublicationConfig: vi.fn(), publishProject: vi.fn() }))
vi.mock('@/api/feedback/projects', () => api)
const person = { userId: 10, nickName: '张三', userName: 'zhangsan', available: true }
function fixture() {
  return {
    projectId: 7, projectName: '流程测试', editable: true, targets: [], evaluatorSelections: [], configuredParticipants: [person],
    relations: [
      { relationCode: 'REL_SELF', relationType: 'SELF', relationName: '自己', isEnabled: true, participatesInScore: false, weight: '0', fixed: true },
      { relationCode: 'REL_PEER', relationType: 'PEER', relationName: '同级', isEnabled: false, participatesInScore: false, weight: '0', fixed: true }
    ],
    validationIssues: [], isPublishReady: false
  }
}
let wrapper, store
async function open(config = fixture(), query = '', mode = 'others') {
  vi.clearAllMocks()
  const pinia = createPinia()
  setActivePinia(pinia)
  useAuthStore().permissions = ['feedback:participant:manage', 'feedback:project:publish', 'feedback:questionnaire:edit']
  api.getPublicationConfig.mockResolvedValue({ data: config })
  api.listParticipantOptions.mockResolvedValue({ rows: [person], total: 1 })
  const router = createRouter({ history: createMemoryHistory(), routes: [
    { path: '/hr/projects/:projectId/publication', component: PublicationConfigView },
    { path: '/hr/projects/:projectId/editor', component: { template: '<div>问卷</div>' } }
  ] })
  await router.push(`/hr/projects/7/publication${query}`)
  wrapper = mount(RouterView, { global: { plugins: [pinia, router, ElementPlus], stubs: { teleport: false } } })
  await flushPromises()
  store = usePublicationConfigStore()
  mockSave()
  if (mode) {
    await wrapper.get(`input[value="${mode}"]`).setValue(true)
    await flushPromises()
  }
  return router
}
async function click(text) {
  const button = [...wrapper.findAll('button'), ...new DOMWrapper(document.body).findAll('.el-drawer button')].find(item => item.text() === text && item.isVisible())
  expect(button, text).toBeTruthy()
  await button.trigger('click')
  await flushPromises()
}
function mockSave({ issues = [] } = {}) {
  api.savePublicationConfig.mockImplementation(async () => ({ data: {
    ...JSON.parse(JSON.stringify(store.config)), isPublishReady: !issues.length, validationIssues: issues,
    preview: { targetCount: 1, evaluatorCount: 1, assignmentCount: 1, targetSummaries: [{ targetUserId: 10, selfCount: 1, nonSelfCount: 0, assignmentCount: 1 }] }
  } }))
}
afterEach(() => { wrapper?.unmount(); vi.restoreAllMocks() })

describe('统一六步中的人员发布引导', () => {
  it('明确选择他评后默认上级60同级40，重新载入保留手动权重', async () => {
    const config = fixture()
    config.relations.push({ relationCode: 'REL_SUPERVISOR', relationType: 'SUPERVISOR', relationName: '上级', isEnabled: false, participatesInScore: false, weight: '0', fixed: true })
    await open(config, '', '')
    expect(store.config.relations.filter(item => item.isEnabled)).toHaveLength(1)
    await wrapper.get('input[value="others"]').setValue(true)
    await flushPromises()
    for (const [code, weight] of [['REL_SUPERVISOR', 60], ['REL_PEER', 40]]) {
      const relation = store.config.relations.find(item => item.relationCode === code)
      expect(relation.isEnabled).toBe(true)
      expect(relation.participatesInScore).toBe(true)
      expect(Number(relation.weight)).toBe(weight)
    }
    expect(store.dirty).toBe(true)
    store.updateRelation('REL_SUPERVISOR', { weight: '70' })
    store.updateRelation('REL_PEER', { weight: '30' })
    await store.save()
    const saved = JSON.parse(JSON.stringify(store.config))
    wrapper.unmount()
    await open(saved)
    expect(Number(store.config.relations.find(item => item.relationCode === 'REL_SUPERVISOR').weight)).toBe(70)
    expect(Number(store.config.relations.find(item => item.relationCode === 'REL_PEER').weight)).toBe(30)
    expect(store.dirty).toBe(false)
  })

  it('组织树新增评价人经真实Store后保留姓名部门与可用状态', async () => {
    await open()
    store.addTarget(person)
    store.updateRelation('REL_PEER', { isEnabled: true, participatesInScore: true, weight: '100' })
    await click('下一步：设置评价关系')
    await click('下一步：谁来评价')
    await click('配置')
    expect(new DOMWrapper(document.body).get('[role="dialog"]').text()).toContain('配置评价人 · 张三')
    const transfer = wrapper.findAllComponents({ name: 'TargetSelectorPanel' }).find(item => !item.props('showHeading'))
    const colleague = { userId: 119, userName: 'test119', nickName: '真实姓名', deptName: '研发部', available: true }
    transfer.vm.$emit('add', colleague)
    await flushPromises()
    expect(store.participantDirectory.get(119)).toEqual(colleague)
    expect(new DOMWrapper(document.body).get('.el-drawer .selected-column').text()).toContain('真实姓名')
    expect(new DOMWrapper(document.body).get('.el-drawer .selected-column').text()).toContain('研发部')
    expect(new DOMWrapper(document.body).get('.el-drawer .selected-column').text()).not.toContain('失效')
    const missing = { ...colleague, userId: 120, nickName: '补全姓名' }
    store.setEvaluatorIds(10, 'REL_PEER', [119, 120])
    api.listParticipantOptions.mockResolvedValueOnce({ rows: [missing], total: 1 })
    await transfer.props('loadPeople')({ deptId: 2, pageNum: 1, pageSize: 50 })
    await flushPromises()
    expect(store.participantDirectory.get(120)).toEqual(missing)
    expect(new DOMWrapper(document.body).get('.el-drawer .selected-column').text()).toContain('补全姓名')
    expect(new DOMWrapper(document.body).get('.el-drawer .selected-column').text()).not.toContain('失效')
    await click('完成')
    await click('配置')
    expect(store.evaluatorIds(10, 'REL_PEER')).toEqual([119, 120])
  })

  it('已有被评价人但未启用他评时不默认仅自评，明确选择前阻止前进', async () => {
    const config = fixture()
    config.targets = [person]
    config.isPublishReady = true
    await open(config, '', '')
    expect(wrapper.get('input[value="self"]').element.checked).toBe(false)
    expect(wrapper.get('input[value="others"]').element.checked).toBe(false)
    expect(wrapper.get('[aria-current="step"]').text()).toBe('设置评价关系')
    await click('下一步：谁来评价')
    expect(api.savePublicationConfig).not.toHaveBeenCalled()
    await vi.waitFor(() => expect(wrapper.get('.evaluation-mode').text()).toContain('请选择评价方式'))
    await wrapper.get('input[value="self"]').setValue(true)
    await flushPromises()
    await click('保存并检查发布条件')
    expect(api.savePublicationConfig).toHaveBeenCalledOnce()
    expect(wrapper.get('.preview-panel').isVisible()).toBe(true)
  })

  it('下一步保存失败停留原步，重试等待保存完成且不重复请求', async () => {
    await open()
    store.addTarget(person)
    api.savePublicationConfig.mockRejectedValueOnce(new Error('保存失败'))
    await click('下一步：设置评价关系')
    expect(wrapper.get('[aria-current="step"]').text()).toBe('评价谁')
    expect(store.dirty).toBe(true)
    let finishSave
    api.savePublicationConfig.mockImplementationOnce(() => new Promise(resolve => { finishSave = resolve }))
    await click('下一步：设置评价关系')
    await click('下一步：设置评价关系')
    expect(api.savePublicationConfig).toHaveBeenCalledTimes(2)
    expect(wrapper.get('[aria-current="step"]').text()).toBe('评价谁')
    finishSave({ data: JSON.parse(JSON.stringify(store.config)) })
    await flushPromises()
    expect(wrapper.get('[aria-current="step"]').text()).toBe('设置评价关系')
    expect(store.dirty).toBe(false)
  })

  it('沿用六步编号，直接进入后续步骤仍校验前置条件', async () => {
    await open(fixture(), '?step=6')
    const steps = wrapper.get('[aria-label="评价准备流程"]')
    expect(steps.findAll('.el-step')).toHaveLength(6)
    expect(steps.get('[aria-current="step"]').text()).toBe('评价谁')
    expect(wrapper.get('.action-bar').text()).toContain('第 3 步：评价谁')
    expect(api.savePublicationConfig).not.toHaveBeenCalled()
    await steps.get('[aria-label="第6步：检查并发布"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('.selector-panel').isVisible()).toBe(true)
  })

  it('返回指标经过未保存确认，取消保留人员配置，确认进入指标步骤', async () => {
    const router = await open()
    store.addTarget(person)
    vi.spyOn(ElMessageBox, 'confirm').mockRejectedValueOnce('cancel').mockResolvedValueOnce('confirm')
    await wrapper.get('[aria-label="第2步：配置指标与权重"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/hr/projects/7/publication')
    expect(store.config.targets).toHaveLength(1)
    await wrapper.get('[aria-label="第2步：配置指标与权重"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/hr/projects/7/editor?step=2')
  })
  it('未选人时阻止跳步，前三步不显示发布按钮', async () => {
    await open()
    await click('下一步：设置评价关系')
    expect(wrapper.get('.selector-panel').isVisible()).toBe(true)
    expect(wrapper.findAll('button').some(item => item.text() === '发布项目')).toBe(false)
    expect(api.savePublicationConfig).not.toHaveBeenCalled()
  })

  it('来回切换保留关系和已分配人员，权重不满足时阻止前进', async () => {
    await open()
    store.addTarget(person)
    await click('下一步：设置评价关系')
    store.updateRelation('REL_PEER', { isEnabled: true, participatesInScore: true, weight: '80' })
    await click('下一步：谁来评价')
    expect(wrapper.get('.relation-panel').isVisible()).toBe(true)
    store.updateRelation('REL_PEER', { weight: '100' })
    await click('下一步：谁来评价')
    await click('保存并检查发布条件')
    expect(wrapper.get('.evaluator-panel').isVisible()).toBe(true)
    expect(api.savePublicationConfig).toHaveBeenCalledTimes(2)
    store.setEvaluatorIds(10, 'REL_PEER', [11])
    await click('上一步')
    await click('上一步')
    await click('下一步：设置评价关系')
    await click('下一步：谁来评价')
    expect(store.evaluatorIds(10, 'REL_PEER')).toEqual([11])
    await click('配置')
    expect(new DOMWrapper(document.body).get('.el-drawer .selected-column').text()).toContain('已选同级评价人（1）')
  })

  it('仅自评分支跳过分配，保存失败保留本步及草稿，成功后展示最新检查', async () => {
    await open()
    store.addTarget(person)
    await click('下一步：设置评价关系')
    expect(wrapper.get('.evaluation-mode').text()).toContain('李四作为上级评价张三')
    await wrapper.get('input[value="self"]').setValue(true)
    await flushPromises()
    expect(wrapper.get('.evaluation-mode').text()).toContain('张三既是被评价人，也是评价人，评价关系为“自评”')
    expect(wrapper.get('.evaluation-mode').text()).not.toContain('李四作为上级评价张三')
    store.markDirty()
    api.savePublicationConfig.mockRejectedValueOnce(new Error('保存失败'))
    await click('保存并检查发布条件')
    expect(wrapper.get('.evaluation-mode').isVisible()).toBe(true)
    expect(store.dirty).toBe(true)
    mockSave()
    await click('保存并检查发布条件')
    expect(wrapper.get('.preview-panel').isVisible()).toBe(true)
    expect(wrapper.get('[aria-current="step"]').text()).toBe('检查并发布')
    expect(wrapper.get('[aria-label="第5步：谁来评价"]').element.disabled).toBe(true)
    expect(wrapper.get('.preparation-steps').text()).toContain('无需配置')
    expect(wrapper.get('.preview-panel').text()).toContain('张三')
    expect(api.savePublicationConfig.mock.calls.at(-1)[1].evaluatorSelections).toEqual([])
    expect([...wrapper.findAll('button'), ...new DOMWrapper(document.body).findAll('.el-drawer button')].find(item => item.text() === '发布项目').element.disabled).toBe(false)
    await click('上一步')
    expect(wrapper.get('.evaluation-mode').isVisible()).toBe(true)
    expect(store.config.targets).toHaveLength(1)
    await wrapper.get('input[value="others"]').setValue(true)
    await flushPromises()
    expect(wrapper.get('.evaluation-mode').text()).toContain('李四作为上级评价张三')
    expect(wrapper.get('.evaluation-mode').text()).not.toContain('张三既是被评价人')
  })

  it('修改使已保存检查过期，回到检查页不能发布，问题入口跳回对应步骤', async () => {
    const config = fixture()
    config.targets = [person]
    config.isPublishReady = true
    config.relations[1] = { ...config.relations[1], isEnabled: true, participatesInScore: true, weight: '100' }
    await open(config)
    store.addTarget({ userId: 12, nickName: '新员工' })
    await flushPromises()
    expect(wrapper.get('.preview-panel').text()).toContain('需要重新检查')
    expect([...wrapper.findAll('button'), ...new DOMWrapper(document.body).findAll('.el-drawer button')].find(item => item.text() === '发布项目').element.disabled).toBe(true)
    mockSave({ issues: [{ code: 'TARGET_USER_UNAVAILABLE', path: 'targets.1', message: '新员工不可用' }] })
    await click('保存并重新检查')
    await click('去处理')
    expect(wrapper.get('.selector-panel').isVisible()).toBe(true)
    expect(store.config.targets).toHaveLength(2)
  })

  it('切换仅自评前确认，取消不移除任何他评配置', async () => {
    await open()
    store.addTarget(person)
    store.updateRelation('REL_PEER', { isEnabled: true, participatesInScore: true, weight: '100' })
    store.setEvaluatorIds(10, 'REL_PEER', [11])
    await click('下一步：设置评价关系')
    vi.spyOn(ElMessageBox, 'confirm').mockRejectedValueOnce('cancel').mockResolvedValueOnce('confirm')
    await wrapper.get('input[value="self"]').setValue(true)
    await flushPromises()
    expect(store.evaluatorIds(10, 'REL_PEER')).toEqual([11])
    await wrapper.get('input[value="self"]').setValue(true)
    await flushPromises()
    expect(store.evaluatorIds(10, 'REL_PEER')).toEqual([])
    expect(store.config.relations.find(item => item.relationCode === 'REL_PEER').isEnabled).toBe(false)
  })
})

describe('关系和人员配置提示', () => {
  it('以定点数合计权重，每位员工必须配齐启用关系', () => {
    const config = fixture()
    config.targets = [person, { userId: 12, nickName: '王五' }]
    config.relations[1] = { ...config.relations[1], isEnabled: true, participatesInScore: true, weight: '33.3333' }
    config.relations.push({ ...config.relations[1], relationCode: 'REL_OTHER', relationName: '其他', weight: '66.6667' })
    config.evaluatorSelections = [
      { targetUserId: 10, relationCode: 'REL_PEER', evaluatorUserIds: [11] },
      { targetUserId: 10, relationCode: 'REL_OTHER', evaluatorUserIds: [13] }
    ]
    const state = analyzePublicationWorkflow(config)
    expect(state.totalWeight).toBe(100)
    expect(state.assignmentIssues).toHaveLength(2)
    expect(state.assignmentIssues.map(item => item.targetUserId)).toEqual([12, 12])
    expect(state.targetSummaries[1].missingScoring).toBe(true)
    config.relations[2].weight = '80'
    expect(analyzePublicationWorkflow(config).relationIssues[0]).toContain('113.3333%')
  })
  it('其他人已配齐不能抵消当前员工缺失关系，补齐后才通过', () => {
    const config = fixture()
    config.targets = [person, { userId: 12, nickName: '王五' }]
    config.relations[1] = { ...config.relations[1], isEnabled: true, participatesInScore: true, weight: '100' }
    config.relations.push({ ...config.relations[1], relationCode: 'REL_UPPER', relationName: '上级', participatesInScore: false, weight: '0' })
    config.evaluatorSelections = [
      { targetUserId: 10, relationCode: 'REL_PEER', evaluatorUserIds: [11] },
      { targetUserId: 10, relationCode: 'REL_UPPER', evaluatorUserIds: [13] },
      { targetUserId: 12, relationCode: 'REL_PEER', evaluatorUserIds: [11] }
    ]
    expect(analyzePublicationWorkflow(config).assignmentIssues).toEqual([
      { message: '“王五”尚未配置“上级”评价人', targetUserId: 12, relationCode: 'REL_UPPER' }
    ])
    expect(publicationIssueDestination({ code: 'TARGET_RELATION_ASSIGNMENT_REQUIRED', path: 'targets.1.relations.REL_UPPER' })).toBe(2)
    config.evaluatorSelections.push({ targetUserId: 12, relationCode: 'REL_UPPER', evaluatorUserIds: [13] })
    expect(analyzePublicationWorkflow(config).assignmentIssues).toEqual([])
  })
  it('正权重关系未配人定位到分配步骤，问卷问题定位到编辑器', () => {
    expect(publicationIssueDestination({ code: 'RELATION_POSITIVE_ASSIGNMENT_REQUIRED', path: 'relations.1' })).toBe(2)
    expect(publicationIssueDestination({ code: 'INDICATOR_REQUIRED', path: 'indicators' })).toBe('editor')
  })
})
