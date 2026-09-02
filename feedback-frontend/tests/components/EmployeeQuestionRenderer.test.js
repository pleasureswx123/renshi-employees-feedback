import ElementPlus from 'element-plus'
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import QuestionRenderer from '@/components/feedback/questions/QuestionRenderer.vue'
import { completeAnswers, detailFixture } from '../fixtures/answerSheet'

const questions = detailFixture().questionnaire.pages.flatMap(page => page.questions)
const render = (question, mode, modelValue) => mount(QuestionRenderer, {
  global: { plugins: [ElementPlus] }, props: { question, mode, modelValue }
})

describe('员工五题型与只读语义', () => {
  it.each(questions)('$questionType 的历史答案不可编辑，也不向父级发出修改', question => {
    const wrapper = render(question, 'readonly', completeAnswers()[question.questionCode])
    const child = wrapper.findComponent({ name: {
      SINGLE_CHOICE: 'SingleChoiceQuestion', STAR_RATING: 'StarRatingQuestion',
      NUMERIC_INPUT: 'NumericInputQuestion', SLIDER: 'SliderQuestion', TEXT: 'TextQuestion'
    }[question.questionType] })
    child.vm.$emit('update:modelValue', { value: 99, text: '不能修改' })
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    for (const field of wrapper.findAll('input, textarea')) {
      expect(field.element.disabled || field.element.readOnly).toBe(true)
    }
    if (question.questionType === 'STAR_RATING') expect(wrapper.find('.el-rate').classes()).toContain('is-disabled')
    if (question.questionType === 'SLIDER') expect(wrapper.find('.el-slider__runway').classes()).toContain('is-disabled')
    wrapper.unmount()
  })

  it.each(questions)('$questionType 的空历史答案明确显示未作答，不生成默认答案', question => {
    const wrapper = render(question, 'readonly', {})
    expect(wrapper.text()).toContain('未作答')
    expect(wrapper.findAll('input, textarea')).toHaveLength(0)
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    wrapper.unmount()
  })

  it('合法零星评分保持零值，清空才是未作答', async () => {
    const wrapper = render(questions[1], 'answer', { value: null })
    const rate = wrapper.findComponent({ name: 'ElRate' })
    rate.vm.$emit('change', 1)
    expect(wrapper.emitted('update:modelValue').at(-1)[0]).toEqual({ value: 0 })
    await wrapper.setProps({ modelValue: { value: 0 } })
    expect(rate.props('modelValue')).toBe(1)
    expect(wrapper.text()).toContain('0 分')
    rate.vm.$emit('change', 0)
    expect(wrapper.emitted('update:modelValue').at(-1)[0]).toEqual({ value: null })
    wrapper.unmount()
  })

  it('数值参考默认值不算作答，滑块须主动确认才发出值', async () => {
    const number = render(questions[2], 'answer', { value: null })
    expect(number.get('input').element.value).toBe('')
    expect(number.emitted('update:modelValue')).toBeUndefined()
    const slider = render(questions[3], 'answer', { value: null, touched: false })
    expect(slider.text()).toContain('尚未作答')
    expect(slider.emitted('update:modelValue')).toBeUndefined()
    await slider.findAll('button').find(button => button.text().includes('确认')).trigger('click')
    expect(slider.emitted('update:modelValue').at(-1)[0]).toEqual({ value: 5, touched: true })
    number.unmount()
    slider.unmount()
  })

  it('附加原因按Unicode字符计数，不用浏览器UTF-16长度提前截断', async () => {
    const wrapper = render(questions[0], 'answer', { optionCode: 'O1', reason: '😀'.repeat(500) })
    expect(wrapper.get('textarea').attributes('maxlength')).toBeUndefined()
    expect(wrapper.text()).toContain('500/500 字')
    await wrapper.get('textarea').setValue('😀'.repeat(501))
    expect([...wrapper.emitted('update:modelValue').at(-1)[0].reason]).toHaveLength(501)
    wrapper.unmount()
  })
})
