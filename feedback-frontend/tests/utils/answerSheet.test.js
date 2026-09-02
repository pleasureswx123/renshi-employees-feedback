import { describe, expect, it } from 'vitest'

import { answerErrors, restoreAnswers, serializeAnswers, validateAnswerSheet } from '@/utils/answerSheet'
import { completeAnswers, detailFixture } from '../fixtures/answerSheet'

describe('员工答卷协议', () => {
  it('五题型共用协议，零值有效，序列化只含答案与数据库题目标识', () => {
    const { questionnaire } = detailFixture()
    const answers = completeAnswers()
    expect(validateAnswerSheet(questionnaire, answers)).toEqual([])
    const payload = serializeAnswers(questionnaire, answers)
    expect(payload[1]).toEqual({ questionId: 2, numericValue: '0.0000' })
    expect(payload[2].numericValue).toBe('42.2500')
    expect(JSON.stringify(payload)).not.toContain('rawScore')
    expect(restoreAnswers(detailFixture(1, { answers: payload }))).toEqual(answers)
  })

  it('未操作的默认值不当作答案，草稿可不完整，提交问题定位到页面与题目', () => {
    const detail = detailFixture()
    const empty = restoreAnswers(detail)
    expect(serializeAnswers(detail.questionnaire, empty)).toEqual([])
    expect(validateAnswerSheet(detail.questionnaire, empty, { required: false })).toEqual([])
    expect(validateAnswerSheet(detail.questionnaire, empty)).toHaveLength(5)
    expect(validateAnswerSheet(detail.questionnaire, empty)[2]).toMatchObject({ pageId: 22, questionId: 3 })
  })

  it('校验选项原因、区间、精度、步长及Unicode字数', () => {
    const detail = detailFixture()
    const [option] = detail.questionnaire.pages[0].questions
    const [number, slider, text] = detail.questionnaire.pages[1].questions
    expect(answerErrors(option, { optionCode: 'O1' })).toEqual(['请填写所选选项的附加原因'])
    expect(answerErrors(option, { optionCode: 'O1' }, { required: false })).toEqual([])
    expect(answerErrors(number, { value: 101 })).toEqual(['分值超出允许范围'])
    expect(answerErrors(number, { value: 1.001 })).toEqual(['分值小数位数超过题目限制'])
    expect(answerErrors(slider, { value: 1.2, touched: true })).toEqual(['滑动评分必须落在合法步长上'])
    text.config.maxLength = 2
    expect(answerErrors(text, { text: '字😀' })).toEqual([])
    expect(answerErrors(text, { text: '三个字' })).toEqual(['回答不能超过2字'])
  })
})
