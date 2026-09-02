export const ProjectStatus = Object.freeze({
  PREPARING: 'PREPARING',
  ACTIVE: 'ACTIVE',
  COMPLETED: 'COMPLETED'
})

export const QuestionnaireVersionStatus = Object.freeze({
  DRAFT: 'DRAFT',
  FROZEN: 'FROZEN'
})

export const AssignmentStatus = Object.freeze({
  PENDING: 'PENDING',
  DRAFT: 'DRAFT',
  SUBMITTED: 'SUBMITTED',
  CLOSED_INCOMPLETE: 'CLOSED_INCOMPLETE'
})

export const QuestionType = Object.freeze({
  SINGLE_CHOICE: 'SINGLE_CHOICE',
  STAR_RATING: 'STAR_RATING',
  NUMERIC_INPUT: 'NUMERIC_INPUT',
  SLIDER: 'SLIDER',
  TEXT: 'TEXT'
})

export const AnswerValueType = Object.freeze({
  OPTION: 'OPTION',
  NUMERIC: 'NUMERIC',
  TEXT: 'TEXT'
})

export const AnswerSheetStatus = Object.freeze({
  DRAFT: 'DRAFT',
  SUBMITTED: 'SUBMITTED'
})

export const RelationType = Object.freeze({
  SUPERVISOR: 'SUPERVISOR',
  PEER: 'PEER',
  SUBORDINATE: 'SUBORDINATE',
  SELF: 'SELF',
  OTHER: 'OTHER',
  CUSTOM: 'CUSTOM'
})

export const ScoreResultType = Object.freeze({
  INDICATOR_RELATION: 'INDICATOR_RELATION',
  INDICATOR_COMPOSITE: 'INDICATOR_COMPOSITE',
  PERSON_TOTAL: 'PERSON_TOTAL',
  COVERAGE: 'COVERAGE'
})
