import { getQuestionTypeDefinition } from '@/components/feedback/questions/questionTypeRegistry'
import { compareDecimals, isDecimalOnStep, normalizeDecimal, toScaledInteger } from './fixedDecimal'

export const TASK_STATUS_LABELS = Object.freeze({
  PENDING: '待评价', DRAFT: '已暂存', SUBMITTED: '已提交', CLOSED_INCOMPLETE: '已关闭未完成'
})

export function allQuestions(questionnaire) {
  return (questionnaire?.pages || []).flatMap(page => page.questions.map(question => ({ page, question })))
}

export function hasAnswer(question, answer) {
  const type = getQuestionTypeDefinition(question.questionType)?.answerType
  if (type === 'option') return Boolean(answer?.optionCode)
  if (type === 'text') return Boolean(answer?.text?.trim())
  if (type === 'slider') return Boolean(answer?.touched) && answer?.value != null
  return answer?.value != null && answer.value !== ''
}

export function answerErrors(question, answer, { required = true } = {}) {
  if (!hasAnswer(question, answer)) return required && question.isRequired ? ['请完成这道必答题'] : []
  const type = getQuestionTypeDefinition(question.questionType)?.answerType
  if (type === 'option') {
    const option = question.options.find(item => item.optionCode === answer.optionCode)
    if (!option) return ['请选择有效选项']
    if (required && option.requiresReason && !answer.reason?.trim()) return ['请填写所选选项的附加原因']
    if ([...(answer.reason || '')].length > 500) return ['附加原因不能超过500字']
    return []
  }
  if (type === 'text') {
    return [...answer.text].length > question.config.maxLength ? [`回答不能超过${question.config.maxLength}字`] : []
  }
  try {
    const value = answer.value
    if (compareDecimals(value, question.minScore) < 0 || compareDecimals(value, question.maxScore) > 0) {
      return ['分值超出允许范围']
    }
    if (toScaledInteger(value) % (10 ** (4 - question.decimalPlaces)) !== 0) return ['分值小数位数超过题目限制']
    if (type === 'slider' && !isDecimalOnStep(value, question.minScore, question.config.step)) {
      return ['滑动评分必须落在合法步长上']
    }
    return []
  } catch {
    return ['请输入合法的数值']
  }
}

export function validateAnswerSheet(questionnaire, answers, options) {
  return allQuestions(questionnaire).flatMap(({ page, question }) =>
    answerErrors(question, answers[question.questionCode], options).map(message => ({
      pageId: page.pageId, questionId: question.questionId, questionCode: question.questionCode, message
    }))
  )
}

export function restoreAnswers(detail) {
  const values = new Map(detail.answers.map(answer => [answer.questionId, answer]))
  return Object.fromEntries(allQuestions(detail.questionnaire).map(({ question }) => {
    const value = values.get(question.questionId)
    const type = getQuestionTypeDefinition(question.questionType).answerType
    if (type === 'option') return [question.questionCode, {
      optionCode: question.options.find(option => option.optionId === value?.optionId)?.optionCode || '',
      reason: value?.reason || ''
    }]
    if (type === 'text') return [question.questionCode, { text: value?.textValue || '' }]
    return [question.questionCode, {
      value: value?.numericValue == null ? null : Number(value.numericValue),
      ...(type === 'slider' ? { touched: value?.numericValue != null } : {})
    }]
  }))
}

export function serializeAnswers(questionnaire, answers) {
  return allQuestions(questionnaire).filter(({ question }) => hasAnswer(question, answers[question.questionCode]))
    .map(({ question }) => {
      const answer = answers[question.questionCode]
      const type = getQuestionTypeDefinition(question.questionType).answerType
      if (type === 'option') return {
        questionId: question.questionId,
        optionId: question.options.find(option => option.optionCode === answer.optionCode)?.optionId,
        reason: answer.reason?.trim() || null
      }
      if (type === 'text') return { questionId: question.questionId, textValue: answer.text }
      return { questionId: question.questionId, numericValue: normalizeDecimal(answer.value) }
    })
}
