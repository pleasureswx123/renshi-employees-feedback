export function detailFixture(assignmentId = 1, overrides = {}) {
  const base = { isRequired: true, isScored: true, description: '', options: [], minScore: '0', maxScore: '10', decimalPlaces: 0, config: {} }
  return {
    task: { assignmentId, projectId: 10, projectName: '协作评价', projectStatus: 'ACTIVE', versionId: 20, targetUserId: 100 + assignmentId, targetName: assignmentId === 1 ? '张三' : '李四', targetDeptName: '研发部', relationId: 30, relationName: '同级', status: 'PENDING', savedTime: null, submittedTime: null },
    questionnaire: {
      versionId: 20, title: '五题型评价', description: '', descriptionDoc: null,
      pages: [
        { pageId: 21, pageCode: 'P1', pageTitle: '协作', sortOrder: 1, questions: [
          { ...base, questionId: 1, questionCode: 'Q1', questionType: 'SINGLE_CHOICE', title: '协作评价', options: [
            { optionId: 11, optionCode: 'O1', optionLabel: '很好', score: '3', requiresReason: true },
            { optionId: 12, optionCode: 'O2', optionLabel: '一般', score: '0', requiresReason: false }
          ] },
          { ...base, questionId: 2, questionCode: 'Q2', questionType: 'STAR_RATING', title: '主动性', minScore: '0', maxScore: '5' }
        ] },
        { pageId: 22, pageCode: 'P2', pageTitle: '质量与建议', sortOrder: 2, questions: [
          { ...base, questionId: 3, questionCode: 'Q3', questionType: 'NUMERIC_INPUT', title: '质量评分', maxScore: '100', decimalPlaces: 2, config: { defaultValue: '20' } },
          { ...base, questionId: 4, questionCode: 'Q4', questionType: 'SLIDER', title: '沟通评分', decimalPlaces: 1, config: { step: '0.5', defaultValue: '5' } },
          { ...base, questionId: 5, questionCode: 'Q5', questionType: 'TEXT', title: '建议', isScored: false, config: { maxLength: 100 } }
        ] }
      ]
    },
    sheetId: null, lockVersion: 0, lastPageId: 21, answeredCount: 0, answers: [], editable: true, alreadySubmitted: false,
    ...overrides
  }
}

export const completeAnswers = () => ({
  Q1: { optionCode: 'O1', reason: '主动配合' }, Q2: { value: 0 }, Q3: { value: 42.25 },
  Q4: { value: 4.5, touched: true }, Q5: { text: '继续保持' }
})
