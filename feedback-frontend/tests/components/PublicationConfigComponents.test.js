import ElementPlus from 'element-plus'
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import PublicationPreviewPanel from '@/components/feedback/publication/PublicationPreviewPanel.vue'
import RelationConfigPanel from '@/components/feedback/publication/RelationConfigPanel.vue'

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
  it('展示后端权威预览数量和稳定问题定位', () => {
    const wrapper = mount(PublicationPreviewPanel, {
      global: { plugins: [ElementPlus] },
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

  it('冻结视图禁用关系编辑且不显示增删入口', () => {
    const wrapper = mount(RelationConfigPanel, {
      global: { plugins: [ElementPlus] },
      props: { relations, editable: false }
    })

    expect(wrapper.text()).not.toContain('增加自定义关系')
    expect(wrapper.text()).not.toContain('删除')
    expect(wrapper.findAll('input').every(input => input.attributes('disabled') !== undefined)).toBe(true)
  })
})
