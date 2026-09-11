import { describe, expect, it } from 'vitest'
import { getQuestionTypeDefinition } from '@/components/feedback/questions/questionTypeRegistry'
import { getQuestionnaireWorkflow } from '@/utils/questionnaireWorkflow'

function fixture() {
  return {
    title: '协作评价',
    pages: [{ pageCode: 'P1', pageTitle: '第一页', questions: ['Q1', 'Q2'].map(questionCode => ({
      ...getQuestionTypeDefinition('STAR_RATING').createDefault(), questionCode, title: questionCode
    })) }],
    indicators: [{ indicatorCode: 'I1', indicatorName: '工作能力', weight: '100.0000', questionCodes: ['Q1', 'Q2'] }]
  }
}

describe('问卷到指标的步骤检查', () => {
  it('零权重指标也必须绑定计分题，权重不能留空', () => {
    const draft = fixture()
    draft.indicators.push({ indicatorCode: 'I2', indicatorName: '补充指标', weight: '0', questionCodes: [] })
    expect(getQuestionnaireWorkflow(draft).indicatorIssues).toContain('“补充指标”需要绑定有效计分题')
    draft.indicators[1].weight = null
    expect(getQuestionnaireWorkflow(draft).indicatorIssues).toContain('请填写所有指标权重')
  })

  it('缺题、空题和没有有效计分题时，问卷步骤尚未完成', () => {
    const draft = fixture()
    draft.pages[0].questions[1].title = ''
    expect(getQuestionnaireWorkflow(draft)).toMatchObject({ questionReady: false, invalidQuestionCode: 'Q2' })
    draft.pages[0].questions = []
    expect(getQuestionnaireWorkflow(draft).questionIssues).toContain('请先添加问卷题目')
    draft.pages[0].questions = [{ ...getQuestionTypeDefinition('TEXT').createDefault(), questionCode: 'Q1', title: '建议' }]
    expect(getQuestionnaireWorkflow(draft).questionIssues).toContain('请至少设置一道满分大于0的计分题')
  })

  it('先写完题目，无指标也可完成问卷步骤，但不能完成指标步骤', () => {
    const draft = fixture()
    draft.indicators = []
    expect(getQuestionnaireWorkflow(draft)).toMatchObject({ questionReady: true, indicatorReady: false })
    expect(getQuestionnaireWorkflow(draft).indicatorIssues).toContain('还有2道计分题未绑定指标')
  })

  it.each(['99.9999', '100.0001'])('合计 %s 不满足精确100%%', weight => {
    const draft = fixture()
    draft.indicators[0].weight = weight
    expect(getQuestionnaireWorkflow(draft).indicatorReady).toBe(false)
  })

  it('题目绑定缺失、重复或正权重指标无有效题目时不能进入人员配置', () => {
    const draft = fixture()
    draft.indicators[0].questionCodes = ['Q1']
    expect(getQuestionnaireWorkflow(draft).indicatorIssues).toContain('还有1道计分题未绑定指标')
    draft.indicators.push({ indicatorCode: 'I2', indicatorName: '协作', weight: '0.0000', questionCodes: ['Q1', 'Q2'] })
    expect(getQuestionnaireWorkflow(draft).indicatorIssues).toContain('一道题最多绑定一个指标')
    draft.indicators[0].questionCodes = []
    expect(getQuestionnaireWorkflow(draft).indicatorIssues).toContain('“工作能力”需要绑定有效计分题')
  })

  it('完整绑定及精确100%权重通过，新增题目后重新提示尚未绑定', () => {
    const draft = fixture()
    draft.indicators[0].weight = '33.3333'
    draft.indicators[0].questionCodes = ['Q1']
    draft.indicators.push({ indicatorCode: 'I2', indicatorName: '协作', weight: '66.6667', questionCodes: ['Q2'] })
    expect(getQuestionnaireWorkflow(draft)).toMatchObject({ questionReady: true, indicatorReady: true })
    draft.pages[0].questions.push({ ...getQuestionTypeDefinition('STAR_RATING').createDefault(), questionCode: 'Q3', title: '主动性' })
    expect(getQuestionnaireWorkflow(draft)).toMatchObject({ questionReady: true, indicatorReady: false })
  })
})
