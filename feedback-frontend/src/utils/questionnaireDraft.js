import { getQuestionTypeDefinition } from '@/components/feedback/questions/questionTypeRegistry'
import { compareDecimals, fromScaledInteger, toScaledInteger } from '@/utils/fixedDecimal'

export { createStableCode } from '@/utils/stableCode'
import { createStableCode } from '@/utils/stableCode'

export function createRichTextDocument(text = '') {
  const paragraphs = String(text)
    .split(/\r?\n/)
    .map(line => ({
      type: 'paragraph',
      ...(line ? { content: [{ type: 'text', text: line }] } : {})
    }))
  return { type: 'doc', content: paragraphs.length ? paragraphs : [{ type: 'paragraph' }] }
}

function cloneJson(value) {
  return value == null ? value : JSON.parse(JSON.stringify(value))
}

function normalizePage(page, index) {
  return {
    pageId: page?.pageId ?? null,
    pageCode: page?.pageCode || createStableCode('P'),
    pageTitle: page?.pageTitle ?? `第${index + 1}页`,
    sortOrder: index + 1,
    questions: (page?.questions || []).map((question, questionIndex) => {
      const definition = getQuestionTypeDefinition(question.questionType)
      if (!definition) throw new TypeError(`不支持的题型：${question.questionType}`)
      return definition.normalize({ ...question, sortOrder: questionIndex + 1 })
    })
  }
}

function normalizeIndicator(indicator, index) {
  return {
    indicatorId: indicator?.indicatorId ?? null,
    indicatorCode: indicator?.indicatorCode || createStableCode('I'),
    indicatorName: indicator?.indicatorName ?? `指标${index + 1}`,
    description: indicator?.description ?? '',
    weight: String(indicator?.weight ?? '0.0000'),
    sortOrder: index + 1,
    questionCodes: [...(indicator?.questionCodes || [])]
  }
}

export function normalizeQuestionnaireDraft(draft) {
  if (!draft) return null
  const normalized = {
    ...draft,
    title: draft.title ?? '',
    description: draft.description ?? '',
    descriptionDoc: cloneJson(draft.descriptionDoc) || createRichTextDocument(draft.description || ''),
    settings: cloneJson(draft.settings) || {},
    pages: (draft.pages || []).map(normalizePage),
    indicators: (draft.indicators || []).map(normalizeIndicator),
    validationIssues: [...(draft.validationIssues || [])],
    isPublishReady: Boolean(draft.isPublishReady)
  }
  if (!normalized.pages.length) normalized.pages.push(normalizePage(null, 0))
  return normalizeQuestionOrders(normalized)
}

export function normalizeQuestionOrders(draft) {
  draft.pages.forEach((page, pageIndex) => {
    page.sortOrder = pageIndex + 1
    page.pageTitle = `第${pageIndex + 1}页`
    page.questions.forEach((question, questionIndex) => {
      question.sortOrder = questionIndex + 1
      question.options.forEach((option, optionIndex) => {
        option.sortOrder = optionIndex + 1
      })
    })
  })
  draft.indicators.forEach((indicator, index) => {
    indicator.sortOrder = index + 1
  })
  return draft
}

function duplicateValues(values) {
  return values.length !== new Set(values).size
}

export function validateQuestionnaireDraft(draft) {
  const errors = []
  if (!draft?.title?.trim()) errors.push('请填写问卷标题')
  if (!draft?.pages?.length) errors.push('问卷至少需要一个页面')
  if ((draft?.pages?.length || 0) > 50) errors.push('问卷最多包含50个页面')

  const pageCodes = (draft?.pages || []).map(page => page.pageCode)
  if (duplicateValues(pageCodes)) errors.push('页面标识不能重复')

  const questions = []
  for (const page of draft?.pages || []) {
    if (!page.pageTitle?.trim()) errors.push('请填写所有页面标题')
    questions.push(...page.questions)
    for (const question of page.questions) {
      const definition = getQuestionTypeDefinition(question.questionType)
      if (!definition) {
        errors.push(`不支持的题型：${question.questionType}`)
        continue
      }
      errors.push(...definition.validate(question).map(message => `“${question.title || '未命名题目'}”：${message}`))
    }
  }
  if (questions.length > 500) errors.push('整份问卷最多包含500道题')
  const questionCodes = questions.map(question => question.questionCode)
  if (duplicateValues(questionCodes)) errors.push('题目标识不能重复')

  const indicators = draft?.indicators || []
  if (duplicateValues(indicators.map(indicator => indicator.indicatorCode))) errors.push('指标标识不能重复')
  if (duplicateValues(indicators.map(indicator => indicator.indicatorName.trim()))) errors.push('指标名称不能重复')
  const knownQuestionCodes = new Set(questionCodes)
  const boundQuestionCodes = new Set()
  indicators.forEach(indicator => {
    if (!indicator.indicatorName?.trim()) errors.push('请填写所有指标名称')
    try {
      if (compareDecimals(indicator.weight, 0) < 0 || compareDecimals(indicator.weight, 100) > 0) {
        errors.push(`“${indicator.indicatorName || '未命名指标'}”：权重必须在0至100之间`)
      }
    } catch {
      errors.push(`“${indicator.indicatorName || '未命名指标'}”：权重格式非法`)
    }
    if (duplicateValues(indicator.questionCodes)) errors.push('同一指标不能重复绑定同一道题')
    indicator.questionCodes.forEach(code => {
      if (!knownQuestionCodes.has(code)) errors.push(`“${indicator.indicatorName}”绑定了不存在的题目`)
      if (boundQuestionCodes.has(code)) errors.push('一道题最多绑定一个指标')
      boundQuestionCodes.add(code)
    })
  })

  if (draft?.descriptionDoc && JSON.stringify(draft.descriptionDoc).length > 100 * 1024) {
    errors.push('问卷说明富文本不能超过100KB')
  }
  return [...new Set(errors)]
}

export const validateSingleChoiceDraft = validateQuestionnaireDraft

export function calculateRawMaxScore(draft) {
  const total = (draft?.pages || []).reduce(
    (pageTotal, page) =>
      pageTotal +
      page.questions.reduce((questionTotal, question) => {
        const definition = getQuestionTypeDefinition(question.questionType)
        return questionTotal + (definition ? toScaledInteger(definition.calculateMaxScore(question)) : 0)
      }, 0),
    0
  )
  return fromScaledInteger(total)
}

export function serializeQuestionnaireDraft(draft) {
  normalizeQuestionOrders(draft)
  return {
    versionId: draft.versionId,
    lockVersion: draft.lockVersion,
    title: draft.title,
    description: draft.description || null,
    descriptionDoc: cloneJson(draft.descriptionDoc),
    settings: cloneJson(draft.settings) || {},
    pages: draft.pages.map(page => ({
      pageId: page.pageId ?? null,
      pageCode: page.pageCode,
      pageTitle: page.pageTitle,
      sortOrder: page.sortOrder,
      questions: page.questions.map(question => {
        const definition = getQuestionTypeDefinition(question.questionType)
        if (!definition) throw new TypeError(`不支持的题型：${question.questionType}`)
        return definition.serialize(question)
      })
    })),
    indicators: draft.indicators.map(indicator => ({
      indicatorId: indicator.indicatorId ?? null,
      indicatorCode: indicator.indicatorCode,
      indicatorName: indicator.indicatorName,
      description: indicator.description || null,
      weight: String(indicator.weight),
      sortOrder: indicator.sortOrder,
      questionCodes: [...indicator.questionCodes]
    }))
  }
}
