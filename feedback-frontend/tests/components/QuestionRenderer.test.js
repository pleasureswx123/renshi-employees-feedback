import ElementPlus from 'element-plus'
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import QuestionRenderer from '@/components/feedback/questions/QuestionRenderer.vue'
import { getQuestionTypeDefinition } from '@/components/feedback/questions/questionTypeRegistry'

const question = {
  questionCode: 'Q_1',
  questionType: 'SINGLE_CHOICE',
  title: '目标是否清晰',
  description: '请选择一项',
  isRequired: true,
  isScored: true,
  options: [
    { optionCode: 'O_A', optionLabel: '非常清晰', score: 5, requiresReason: true },
    { optionCode: 'O_B', optionLabel: '一般', score: 3, requiresReason: false }
  ]
}

describe('共享题型渲染器', () => {
  it('注册表把单选题映射到同一渲染组件', () => {
    const definition = getQuestionTypeDefinition('SINGLE_CHOICE')
    expect(definition.label).toBe('单选题')
    expect(definition.renderer).toBeTruthy()
  })

  it('预览选择要求说明的选项后显示原因输入并发出答案', async () => {
    const wrapper = mount(QuestionRenderer, {
      global: { plugins: [ElementPlus] },
      props: { question, mode: 'preview', modelValue: { optionCode: '', reason: '' } }
    })

    await wrapper.findAll('input[type="radio"]')[0].setValue(true)
    const emitted = wrapper.emitted('update:modelValue')
    expect(emitted.at(-1)[0]).toEqual({ optionCode: 'O_A', reason: '' })

    await wrapper.setProps({ modelValue: { optionCode: 'O_A', reason: '' } })
    expect(wrapper.get('textarea').attributes('placeholder')).toContain('原因')
  })

  it('编辑画布使用只读渲染，避免误写预览答案', () => {
    const wrapper = mount(QuestionRenderer, {
      global: { plugins: [ElementPlus] },
      props: { question, mode: 'editor' }
    })

    expect(wrapper.findAll('input[type="radio"]').every(input => input.attributes('disabled') !== undefined)).toBe(true)
    expect(wrapper.text()).toContain('5分')
  })
})
