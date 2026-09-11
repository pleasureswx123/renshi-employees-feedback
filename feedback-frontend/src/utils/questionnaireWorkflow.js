import { getQuestionTypeDefinition } from '@/components/feedback/questions/questionTypeRegistry'
import { compareDecimals, sumDecimals } from '@/utils/fixedDecimal'
import { calculateRawMaxScore, validateQuestionnaireDraft } from '@/utils/questionnaireDraft'

// 只用于编辑步骤提示，进入人员配置前仍以保存接口返回的完整性检查为准。
export function getQuestionnaireWorkflow(draft) {
  if (!draft) return { questionReady: false, indicatorReady: false, questionIssues: ['正在加载问卷'], indicatorIssues: [], invalidQuestionCode: '' }
  const questions = draft.pages.flatMap(page => page.questions)
  const questionIssues = validateQuestionnaireDraft({ ...draft, indicators: [] })
  if (!questions.length) questionIssues.push('请先添加问卷题目')
  else if (compareDecimals(calculateRawMaxScore(draft), 0) <= 0) questionIssues.push('请至少设置一道满分大于0的计分题')
  const invalidQuestion = questions.find(question => getQuestionTypeDefinition(question.questionType)?.validate(question).length)
  const indicatorIssues = validateQuestionnaireDraft(draft).filter(issue => !questionIssues.includes(issue))
  const indicators = draft.indicators
  if (!indicators.length) indicatorIssues.unshift('请添加评价指标，设置权重并绑定计分题')
  else {
    try {
      if (compareDecimals(sumDecimals(indicators.map(indicator => indicator.weight)), 100) !== 0) indicatorIssues.push('指标权重合计须为100%')
    } catch {
      indicatorIssues.push('请填写有效的指标权重')
    }
  }
  const boundCodes = new Set(indicators.flatMap(indicator => indicator.questionCodes))
  const unbound = questions.filter(question => question.isScored && !boundCodes.has(question.questionCode))
  if (unbound.length) indicatorIssues.push(`还有${unbound.length}道计分题未绑定指标`)
  for (const indicator of indicators) {
    const boundQuestions = questions.filter(question => indicator.questionCodes.includes(question.questionCode))
    if (compareDecimals(calculateRawMaxScore({ pages: [{ questions: boundQuestions }] }), 0) <= 0) {
      indicatorIssues.push(`“${indicator.indicatorName || '未命名指标'}”需要绑定有效计分题`)
    }
  }
  return {
    questionReady: questionIssues.length === 0,
    indicatorReady: indicatorIssues.length === 0,
    questionIssues: [...new Set(questionIssues)],
    indicatorIssues: [...new Set(indicatorIssues)],
    invalidQuestionCode: invalidQuestion?.questionCode || ''
  }
}
