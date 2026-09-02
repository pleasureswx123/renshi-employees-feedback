import { describe, expect, it } from 'vitest'

import {
  getQuestionTypeDefinition,
  QUESTION_TYPE_DEFINITIONS
} from '@/components/feedback/questions/questionTypeRegistry'
import {
  calculateRawMaxScore,
  normalizeQuestionnaireDraft,
  serializeQuestionnaireDraft,
  validateQuestionnaireDraft
} from '@/utils/questionnaireDraft'

function draftWithAllTypes() {
  const questions = QUESTION_TYPE_DEFINITIONS.map(definition => definition.createDefault())
  return normalizeQuestionnaireDraft({
    projectId: 7,
    versionId: 9,
    lockVersion: 0,
    title: '五题型问卷',
    description: '',
    settings: {},
    pages: [{ pageCode: 'P_1', pageTitle: '第1页', questions }],
    indicators: []
  })
}

describe('五题型注册表', () => {
  it('完整注册渲染、属性、规范化、校验、序列化和满分能力', () => {
    expect(QUESTION_TYPE_DEFINITIONS.map(item => item.type)).toEqual([
      'SINGLE_CHOICE',
      'STAR_RATING',
      'NUMERIC_INPUT',
      'SLIDER',
      'TEXT'
    ])
    for (const definition of QUESTION_TYPE_DEFINITIONS) {
      expect(definition.renderer).toBeTruthy()
      expect(definition.propertyEditor).toBeTruthy()
      expect(definition.validate(definition.createDefault())).toEqual([])
      expect(definition.serialize(definition.createDefault()).questionType).toBe(definition.type)
      expect(definition.calculateMaxScore(definition.createDefault())).toMatch(/^\d+\.\d{4}$/)
    }
    expect(getQuestionTypeDefinition('UNKNOWN')).toBeNull()
  })

  it('精确计算五题型原始满分，并保持问答题不计分', () => {
    const draft = draftWithAllTypes()
    expect(calculateRawMaxScore(draft)).toBe('116.0000')
    const textQuestion = draft.pages[0].questions.at(-1)
    expect(textQuestion.isScored).toBe(false)
    expect(textQuestion.minScore).toBeNull()
    expect(textQuestion.maxScore).toBeNull()
  })

  it('校验滑块合法步长、星级未作答边界和题型专属配置', () => {
    const slider = getQuestionTypeDefinition('SLIDER').createDefault()
    slider.config.step = '3.0000'
    slider.config.defaultValue = '5.0000'
    expect(getQuestionTypeDefinition('SLIDER').validate(slider)).toContain('滑动评分默认值必须落在合法步长上')

    const star = getQuestionTypeDefinition('STAR_RATING').createDefault()
    star.minScore = '0.0000'
    expect(getQuestionTypeDefinition('STAR_RATING').validate(star)).toContain('星级评分最低分固定为1')

    const text = getQuestionTypeDefinition('TEXT').createDefault()
    text.config.maxLength = 5001
    expect(getQuestionTypeDefinition('TEXT').validate(text)).toContain('问答题最大字数必须在1至5000之间')
  })

  it('序列化完整多页与指标协议，不丢失稳定标识和富文本JSON', () => {
    const draft = draftWithAllTypes()
    draft.descriptionDoc = {
      type: 'doc',
      content: [{ type: 'heading', attrs: { level: 2 }, content: [{ type: 'text', text: '填写说明' }] }]
    }
    draft.indicators.push({
      indicatorId: null,
      indicatorCode: 'I_1',
      indicatorName: '协作',
      description: '',
      weight: '100.0000',
      sortOrder: 1,
      questionCodes: draft.pages[0].questions.filter(item => item.isScored).map(item => item.questionCode)
    })

    expect(validateQuestionnaireDraft(draft)).toEqual([])
    const payload = serializeQuestionnaireDraft(draft)
    expect(payload.descriptionDoc.content[0].type).toBe('heading')
    expect(payload.pages[0].pageCode).toBe('P_1')
    expect(payload.pages[0].questions.map(item => item.questionType)).toHaveLength(5)
    expect(payload.indicators[0].weight).toBe('100.0000')
  })
})
