import { describe, expect, it } from 'vitest'

import {
  AnswerSheetStatus,
  AnswerValueType,
  AssignmentStatus,
  ProjectStatus,
  QuestionnaireVersionStatus,
  QuestionType,
  RelationType,
  ScoreResultType
} from '@/constants/feedbackEnums'

describe('评价领域枚举契约', () => {
  it('与后端和数据库状态、题型及答案值保持一致', () => {
    expect(Object.values(ProjectStatus)).toEqual(['PREPARING', 'ACTIVE', 'COMPLETED'])
    expect(Object.values(QuestionnaireVersionStatus)).toEqual(['DRAFT', 'FROZEN'])
    expect(Object.values(AssignmentStatus)).toEqual(['PENDING', 'DRAFT', 'SUBMITTED', 'CLOSED_INCOMPLETE'])
    expect(Object.values(QuestionType)).toEqual([
      'SINGLE_CHOICE',
      'STAR_RATING',
      'NUMERIC_INPUT',
      'SLIDER',
      'TEXT'
    ])
    expect(Object.values(AnswerValueType)).toEqual(['OPTION', 'NUMERIC', 'TEXT'])
    expect(Object.values(AnswerSheetStatus)).toEqual(['DRAFT', 'SUBMITTED'])
    expect(Object.values(RelationType)).toEqual(['SUPERVISOR', 'PEER', 'SUBORDINATE', 'SELF', 'OTHER', 'CUSTOM'])
    expect(Object.values(ScoreResultType)).toEqual([
      'INDICATOR_RELATION',
      'INDICATOR_COMPOSITE',
      'PERSON_TOTAL',
      'COVERAGE'
    ])
  })

  it('导出的枚举对象不可修改', () => {
    expect(Object.isFrozen(ProjectStatus)).toBe(true)
    expect(Object.isFrozen(AssignmentStatus)).toBe(true)
    expect(Object.isFrozen(QuestionType)).toBe(true)
  })
})
