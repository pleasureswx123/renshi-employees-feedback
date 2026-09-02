let sequence = 0

export function createStableCode(prefix) {
  sequence += 1
  const randomPart = globalThis.crypto?.randomUUID?.().replaceAll('-', '')
  return `${prefix}_${randomPart || `${Date.now()}_${sequence}`}`
}

export function normalizeQuestionOrders(draft) {
  draft.pages.forEach((page, pageIndex) => {
    page.sortOrder = pageIndex + 1
    page.questions.forEach((question, questionIndex) => {
      question.sortOrder = questionIndex + 1
      question.options.forEach((option, optionIndex) => {
        option.sortOrder = optionIndex + 1
      })
    })
  })
  return draft
}

export function validateSingleChoiceDraft(draft) {
  const errors = []
  if (!draft?.title?.trim()) errors.push('请填写问卷标题')
  for (const page of draft?.pages || []) {
    if (!page.pageTitle?.trim()) errors.push('请填写页面标题')
    for (const question of page.questions || []) {
      if (!question.title?.trim()) errors.push('请填写所有单选题标题')
      if ((question.options || []).length < 2) errors.push(`“${question.title || '未命名题目'}”至少需要两个选项`)
      for (const option of question.options || []) {
        if (!option.optionLabel?.trim()) errors.push(`“${question.title || '未命名题目'}”存在空选项`)
        const score = Number(option.score)
        if (!Number.isFinite(score) || score < 0) errors.push('选项分值必须是大于等于0的数字')
      }
    }
  }
  return [...new Set(errors)]
}

export function calculateRawMaxScore(draft) {
  return (draft?.pages || []).reduce(
    (pageTotal, page) =>
      pageTotal +
      (page.questions || []).reduce((questionTotal, question) => {
        if (!question.isScored || question.questionType !== 'SINGLE_CHOICE') return questionTotal
        const scores = (question.options || []).map(option => Number(option.score) || 0)
        return questionTotal + Math.max(0, ...scores)
      }, 0),
    0
  )
}
