export function frozenDetailsFixture() {
  const common = { isRequired: true, isScored: true, decimalPlaces: 0, description: '', config: {}, options: [] }
  return {
    publishedBy: 2, publishedByName: 'feedback-hr', publishedTime: '2026-09-04T15:49:14', versionNo: 1,
    questionnaire: {
      versionId: 201, lockVersion: 3, title: '发布时的360评价问卷', description: '发布时的问卷说明', descriptionDoc: null,
      pages: [
        { pageCode: 'P1', pageTitle: '工作表现', questions: [
          { ...common, questionCode: 'Q1', title: '协作评价', questionType: 'SINGLE_CHOICE', options: [
            { optionCode: 'A', optionLabel: '表现很好', score: '5.0000', requiresReason: true },
            { optionCode: 'B', optionLabel: '需要提升', score: '1.0000' }
          ] },
          { ...common, questionCode: 'Q2', title: '工作质量', questionType: 'STAR_RATING', minScore: '0', maxScore: '5' }
        ] },
        { pageCode: 'P2', pageTitle: '综合反馈', questions: [
          { ...common, questionCode: 'Q3', title: '目标达成', questionType: 'NUMERIC_INPUT', minScore: '0', maxScore: '100', decimalPlaces: 2, config: { defaultValue: '50.5' } },
          { ...common, questionCode: 'Q4', title: '主动协作', questionType: 'SLIDER', minScore: '0', maxScore: '10', config: { step: '1' } },
          { ...common, questionCode: 'Q5', title: '其他建议', questionType: 'TEXT', isScored: false, config: { maxLength: 1000 } }
        ] }
      ],
      indicators: [
        { indicatorCode: 'I1', indicatorName: '工作能力', weight: '70.0000', questionCodes: ['Q1', 'Q2', 'Q3'] },
        { indicatorCode: 'I2', indicatorName: '团队协作', weight: '30.0000', description: '协作表现', questionCodes: ['Q4'] }
      ]
    }
  }
}
