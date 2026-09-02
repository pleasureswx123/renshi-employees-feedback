import { markRaw } from 'vue'

import {
  compareDecimals,
  fromScaledInteger,
  isDecimalOnStep,
  normalizeDecimal,
  toScaledInteger
} from '@/utils/fixedDecimal'
import { createStableCode } from '@/utils/stableCode'

import NumericInputQuestion from './NumericInputQuestion.vue'
import ScoreRangeProperties from './ScoreRangeProperties.vue'
import SingleChoiceProperties from './SingleChoiceProperties.vue'
import SingleChoiceQuestion from './SingleChoiceQuestion.vue'
import SliderQuestion from './SliderQuestion.vue'
import StarRatingQuestion from './StarRatingQuestion.vue'
import TextProperties from './TextProperties.vue'
import TextQuestion from './TextQuestion.vue'

function decimal(value, fallback = 0) {
  try {
    return normalizeDecimal(value ?? fallback)
  } catch {
    return normalizeDecimal(fallback)
  }
}

function commonQuestion(question, defaults) {
  return {
    questionId: question?.questionId ?? null,
    questionCode: question?.questionCode || createStableCode('Q'),
    questionType: defaults.questionType,
    title: question?.title ?? defaults.title,
    description: question?.description ?? '',
    isRequired: Boolean(question?.isRequired),
    isScored: defaults.questionType === 'TEXT' ? false : question?.isScored !== false,
    sortOrder: Number(question?.sortOrder) || 1
  }
}

function normalizeOption(option, index) {
  return {
    optionId: option?.optionId ?? null,
    optionCode: option?.optionCode || createStableCode('O'),
    optionLabel: option?.optionLabel ?? `选项${index + 1}`,
    score: decimal(option?.score),
    requiresReason: Boolean(option?.requiresReason),
    sortOrder: index + 1
  }
}

function validateCommon(question) {
  return question.title?.trim() ? [] : ['请填写题目标题']
}

function precisionValid(value, decimalPlaces) {
  const factor = 10 ** (4 - decimalPlaces)
  return toScaledInteger(value) % factor === 0
}

function normalizeSingleChoice(question = {}) {
  const sourceOptions = question.options?.length
    ? question.options
    : [
        { optionLabel: '选项1', score: 1 },
        { optionLabel: '选项2', score: 0 }
      ]
  return {
    ...commonQuestion(question, { questionType: 'SINGLE_CHOICE', title: '新的单选题' }),
    minScore: null,
    maxScore: null,
    decimalPlaces: 0,
    config: {},
    options: sourceOptions.map(normalizeOption)
  }
}

function validateSingleChoice(question) {
  const errors = validateCommon(question)
  if (question.options.length < 2) errors.push('单选题至少需要两个选项')
  if (new Set(question.options.map(option => option.optionCode)).size !== question.options.length) {
    errors.push('同一题目的选项标识不能重复')
  }
  question.options.forEach(option => {
    if (!option.optionLabel?.trim()) errors.push('单选题存在空选项')
    if (compareDecimals(option.score, 0) < 0) errors.push('选项分值必须大于等于0')
  })
  return [...new Set(errors)]
}

function normalizeScoreRange(question = {}, defaults) {
  return {
    ...commonQuestion(question, defaults),
    minScore: decimal(question.minScore, defaults.minScore),
    maxScore: decimal(question.maxScore, defaults.maxScore),
    decimalPlaces: Number.isInteger(question.decimalPlaces)
      ? question.decimalPlaces
      : defaults.decimalPlaces,
    config: { ...(defaults.config || {}), ...(question.config || {}) },
    options: []
  }
}

function validateScoreRange(question) {
  const errors = validateCommon(question)
  if (!Number.isInteger(question.decimalPlaces) || question.decimalPlaces < 0 || question.decimalPlaces > 4) {
    errors.push('小数位数必须在0至4之间')
  }
  if (compareDecimals(question.minScore, 0) < 0) errors.push('最低分必须大于等于0')
  if (compareDecimals(question.maxScore, question.minScore) <= 0) errors.push('最高分必须大于最低分')
  if (
    Number.isInteger(question.decimalPlaces) &&
    (!precisionValid(question.minScore, question.decimalPlaces) ||
      !precisionValid(question.maxScore, question.decimalPlaces))
  ) {
    errors.push('评分区间精度不能超过允许小数位数')
  }
  return errors
}

function optionalDefaultErrors(question, label) {
  const value = question.config.defaultValue
  if (value == null) return []
  const errors = []
  if (compareDecimals(value, question.minScore) < 0 || compareDecimals(value, question.maxScore) > 0) {
    errors.push(`${label}默认值必须位于评分区间内`)
  }
  if (!precisionValid(value, question.decimalPlaces)) {
    errors.push(`${label}默认值精度不能超过允许小数位数`)
  }
  return errors
}

function maxScore(question) {
  return question.isScored ? decimal(question.maxScore) : '0.0000'
}

function cloneNormalized(normalize, question) {
  return normalize(JSON.parse(JSON.stringify(question)))
}

const singleChoice = {
  type: 'SINGLE_CHOICE',
  label: '单选题',
  description: '从多个选项中选择一项，可配置分值和附加原因。',
  answerType: 'option',
  renderer: markRaw(SingleChoiceQuestion),
  propertyEditor: markRaw(SingleChoiceProperties),
  createDefault: () => normalizeSingleChoice(),
  normalize: normalizeSingleChoice,
  validate: validateSingleChoice,
  serialize: normalizeSingleChoice,
  calculateMaxScore(question) {
    if (!question.isScored) return '0.0000'
    const maximum = Math.max(0, ...question.options.map(option => toScaledInteger(option.score)))
    return fromScaledInteger(maximum)
  },
  clone: question => cloneNormalized(normalizeSingleChoice, question)
}

const starRating = {
  type: 'STAR_RATING',
  label: '星级评分',
  description: '使用2至10颗星快速评分，未点选时保持未作答。',
  answerType: 'number',
  renderer: markRaw(StarRatingQuestion),
  propertyEditor: markRaw(ScoreRangeProperties),
  createDefault: () => starRating.normalize(),
  normalize(question = {}) {
    return normalizeScoreRange(question, {
      questionType: 'STAR_RATING',
      title: '新的星级评分题',
      minScore: 1,
      maxScore: 5,
      decimalPlaces: 0,
      config: {}
    })
  },
  validate(question) {
    const errors = validateScoreRange(question)
    if (compareDecimals(question.minScore, 1) !== 0) errors.push('星级评分最低分固定为1')
    if (!precisionValid(question.maxScore, 0)) errors.push('星级数量必须是整数')
    const stars = toScaledInteger(question.maxScore) / 10000
    if (stars < 2 || stars > 10) errors.push('星级数量必须在2至10之间')
    return [...new Set(errors)]
  },
  serialize(question) {
    return starRating.normalize(question)
  },
  calculateMaxScore: maxScore,
  clone: question => cloneNormalized(starRating.normalize, question)
}

const numericInput = {
  type: 'NUMERIC_INPUT',
  label: '数字输入',
  description: '在限定区间和精度内输入正式分值。',
  answerType: 'number',
  renderer: markRaw(NumericInputQuestion),
  propertyEditor: markRaw(ScoreRangeProperties),
  createDefault: () => numericInput.normalize(),
  normalize(question = {}) {
    const normalized = normalizeScoreRange(question, {
      questionType: 'NUMERIC_INPUT',
      title: '新的数字输入题',
      minScore: 0,
      maxScore: 100,
      decimalPlaces: 2,
      config: { defaultValue: null }
    })
    normalized.config.defaultValue =
      normalized.config.defaultValue == null ? null : decimal(normalized.config.defaultValue)
    return normalized
  },
  validate(question) {
    return [...new Set([...validateScoreRange(question), ...optionalDefaultErrors(question, '数字输入题')])]
  },
  serialize(question) {
    return numericInput.normalize(question)
  },
  calculateMaxScore: maxScore,
  clone: question => cloneNormalized(numericInput.normalize, question)
}

const slider = {
  type: 'SLIDER',
  label: '滑动评分',
  description: '按指定步长滑动评分，并明确区分默认显示与已作答。',
  answerType: 'slider',
  renderer: markRaw(SliderQuestion),
  propertyEditor: markRaw(ScoreRangeProperties),
  createDefault: () => slider.normalize(),
  normalize(question = {}) {
    const normalized = normalizeScoreRange(question, {
      questionType: 'SLIDER',
      title: '新的滑动评分题',
      minScore: 0,
      maxScore: 10,
      decimalPlaces: 1,
      config: { step: 1, defaultValue: null }
    })
    normalized.config.step = decimal(normalized.config.step, 1)
    normalized.config.defaultValue =
      normalized.config.defaultValue == null ? null : decimal(normalized.config.defaultValue)
    return normalized
  },
  validate(question) {
    const errors = [...validateScoreRange(question), ...optionalDefaultErrors(question, '滑动评分')]
    if (compareDecimals(question.config.step, 0) <= 0) errors.push('滑动步长必须大于0')
    const range = fromScaledInteger(toScaledInteger(question.maxScore) - toScaledInteger(question.minScore))
    if (compareDecimals(question.config.step, range) > 0) errors.push('滑动步长不能大于评分区间')
    if (!precisionValid(question.config.step, question.decimalPlaces)) {
      errors.push('滑动步长精度不能超过允许小数位数')
    }
    if (
      question.config.defaultValue != null &&
      !isDecimalOnStep(question.config.defaultValue, question.minScore, question.config.step)
    ) {
      errors.push('滑动评分默认值必须落在合法步长上')
    }
    return [...new Set(errors)]
  },
  serialize(question) {
    return slider.normalize(question)
  },
  calculateMaxScore: maxScore,
  clone: question => cloneNormalized(slider.normalize, question)
}

const textQuestion = {
  type: 'TEXT',
  label: '问答题',
  description: '收集文字反馈，不参与正式计分。',
  answerType: 'text',
  renderer: markRaw(TextQuestion),
  propertyEditor: markRaw(TextProperties),
  createDefault: () => textQuestion.normalize(),
  normalize(question = {}) {
    return {
      ...commonQuestion(question, { questionType: 'TEXT', title: '新的问答题' }),
      isScored: false,
      minScore: null,
      maxScore: null,
      decimalPlaces: 0,
      config: {
        maxLength: Math.min(5000, Math.max(1, Number(question.config?.maxLength) || 1000))
      },
      options: []
    }
  },
  validate(question) {
    const errors = validateCommon(question)
    if (question.isScored) errors.push('问答题不能参与计分')
    if (!Number.isInteger(question.config.maxLength) || question.config.maxLength < 1 || question.config.maxLength > 5000) {
      errors.push('问答题最大字数必须在1至5000之间')
    }
    return errors
  },
  serialize(question) {
    return textQuestion.normalize(question)
  },
  calculateMaxScore: () => '0.0000',
  clone: question => cloneNormalized(textQuestion.normalize, question)
}

export const QUESTION_TYPE_REGISTRY = Object.freeze({
  SINGLE_CHOICE: Object.freeze(singleChoice),
  STAR_RATING: Object.freeze(starRating),
  NUMERIC_INPUT: Object.freeze(numericInput),
  SLIDER: Object.freeze(slider),
  TEXT: Object.freeze(textQuestion)
})

export const QUESTION_TYPE_DEFINITIONS = Object.freeze(Object.values(QUESTION_TYPE_REGISTRY))

export function getQuestionTypeDefinition(questionType) {
  return QUESTION_TYPE_REGISTRY[questionType] || null
}
