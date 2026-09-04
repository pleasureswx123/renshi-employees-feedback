import { expect, test } from '@playwright/test'

const userInfo = {
  code: 200,
  msg: '操作成功',
  user: { userId: 2, userName: 'feedback-hr', nickName: '评价HR' },
  roles: ['feedback_hr'],
  permissions: [
    'feedback:project:list',
    'feedback:project:add',
    'feedback:project:edit',
    'feedback:project:remove',
    'feedback:questionnaire:edit'
  ]
}

function initialDraft() {
  return {
    projectId: 101,
    projectName: '2026年度管理能力评价',
    projectStatus: 'PREPARING',
    versionId: 201,
    versionNo: 1,
    versionStatus: 'DRAFT',
    lockVersion: 0,
    title: '2026年度管理能力评价',
    description: '',
    descriptionDoc: { type: 'doc', content: [{ type: 'paragraph' }] },
    settings: {},
    pages: [
      {
        pageId: 301,
        pageCode: 'P_INITIAL',
        pageTitle: '第1页',
        sortOrder: 1,
        questions: []
      }
    ],
    indicators: [],
    isPublishReady: false,
    validationIssues: [
      { code: 'QUESTIONNAIRE_NO_QUESTIONS', path: 'pages', message: '问卷至少需要一道题' }
    ]
  }
}

test('HR完成P4五题型、多页、指标、保存重载和PC分页实时预览', async ({ page }) => {
  let persistedDraft = initialDraft()
  let saveCount = 0
  let draftReadCount = 0

  await page.route('**/dev-api/transport/crypto/frontend-config', route =>
    route.fulfill({
      json: {
        code: 200,
        data: {
          transportCryptoEnabled: false,
          transportCryptoMode: 'off',
          transportCryptoActive: false,
          configExpireAt: Math.floor(Date.now() / 1000) + 300
        }
      }
    })
  )
  await page.route('**/dev-api/captchaImage', route =>
    route.fulfill({ json: { code: 200, captchaEnabled: false } })
  )
  await page.route('**/dev-api/login', route =>
    route.fulfill({ json: { code: 200, token: 'p4-e2e-token' } })
  )
  await page.route('**/dev-api/getInfo', route => route.fulfill({ json: userInfo }))

  const handleFeedbackApi = async route => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname.replace('/dev-api', '')
    if (path === '/feedback/projects' && request.method() === 'GET') {
      return route.fulfill({
        json: { code: 200, rows: [], pageNum: 1, pageSize: 10, total: 0, hasNext: false }
      })
    }
    if (path === '/feedback/projects' && request.method() === 'POST') {
      return route.fulfill({
        json: {
          code: 200,
          msg: '项目创建成功',
          data: { projectId: 101, projectName: '2026年度管理能力评价', lockVersion: 0 }
        }
      })
    }
    if (path === '/feedback/projects/101/questionnaire-draft' && request.method() === 'GET') {
      draftReadCount += 1
      return route.fulfill({ json: { code: 200, data: persistedDraft } })
    }
    if (path === '/feedback/projects/101/questionnaire-draft' && request.method() === 'PUT') {
      saveCount += 1
      const payload = request.postDataJSON()
      let questionId = 400
      let optionId = 500
      persistedDraft = {
        ...persistedDraft,
        ...payload,
        description: '请依据最近半年的实际协作表现作答',
        lockVersion: payload.lockVersion + 1,
        isPublishReady: false,
        validationIssues: [
          {
            code: 'SCORED_QUESTION_INDICATOR_REQUIRED',
            path: 'pages.0.questions.1',
            message: '仍有计分题未绑定指标'
          }
        ],
        pages: payload.pages.map((pageItem, pageIndex) => ({
          ...pageItem,
          pageId: pageItem.pageId || 301 + pageIndex,
          questions: pageItem.questions.map(question => ({
            ...question,
            questionId: question.questionId || questionId++,
            options: question.options.map(option => ({
              ...option,
              optionId: option.optionId || optionId++
            }))
          }))
        })),
        indicators: payload.indicators.map((indicator, index) => ({
          ...indicator,
          indicatorId: indicator.indicatorId || 601 + index
        }))
      }
      return route.fulfill({ json: { code: 200, msg: '问卷草稿已保存', data: persistedDraft } })
    }
    return route.fulfill({ status: 404, json: { code: 404, msg: '未匹配测试接口' } })
  }
  await page.route('**/dev-api/feedback/projects*', handleFeedbackApi)
  await page.route('**/dev-api/feedback/projects/**', handleFeedbackApi)

  await page.goto('/login')
  await page.getByLabel('账号').fill('feedback-hr')
  await page.getByLabel('密码').fill('secret')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL(/\/hr\/projects$/)

  await page.getByRole('button', { name: '创建项目' }).click()
  const projectDialog = page.getByRole('dialog', { name: '创建评价项目' })
  await projectDialog.getByLabel('项目名称').fill('2026年度管理能力评价')
  await projectDialog.getByLabel('项目说明').fill('验证P4问卷与指标设计器')
  await projectDialog.getByRole('button', { name: '创建并编辑问卷' }).click()

  await expect(page).toHaveURL(/\/hr\/projects\/101\/editor$/)
  await expect(page.getByRole('heading', { name: '问卷与指标设计器' })).toBeVisible()
  await expect(page.getByRole('tab', { name: '题目属性', exact: true })).toHaveAttribute('aria-selected', 'true')
  const propertiesWidth = (await page.locator('.right-panel').boundingBox()).width
  await page.getByRole('tab', { name: '实时预览', exact: true }).click()
  expect((await page.locator('.right-panel').boundingBox()).width).toBeGreaterThan(propertiesWidth)
  await page.getByRole('tab', { name: '题目属性', exact: true }).click()
  expect((await page.locator('.right-panel').boundingBox()).width).toBe(propertiesWidth)
  await page.getByRole('tab', { name: '实时预览', exact: true }).click()
  await page.locator('.canvas-panel .tiptap').fill('请依据最近半年的实际协作表现作答')
  const livePreview = page.getByRole('tabpanel', { name: '实时预览', exact: true })
  await expect(livePreview.getByText('请依据最近半年的实际协作表现作答')).toBeVisible()

  for (const label of ['单选题', '星级评分', '数字输入', '滑动评分']) {
    await page.getByRole('button', { name: new RegExp(`^${label}`) }).click()
    await page.locator('.question-card.active').getByLabel('题目内容').fill(`请评价近期工作表现（${label}）`)
    await expect(livePreview.getByText(`请评价近期工作表现（${label}）`, { exact: true })).toBeVisible()
    if (['数字输入', '滑动评分'].includes(label)) {
      await expect(page.getByRole('spinbutton', { name: '小数位数', exact: true })).toHaveValue('0')
    }
  }
  await expect(page.locator('.question-card')).toHaveCount(4)

  await page.getByRole('button', { name: '增加页面' }).click()
  await page.getByRole('button', { name: /^问答题/ }).click()
  await page.getByLabel('题目内容').fill('请给出一项最具体的改进建议')
  await expect(page.locator('.question-card')).toHaveCount(1)
  await expect(page.locator('.outline-question.active')).toHaveText('5. 请给出一项最具体的改进建议')
  await expect(page.locator('.question-card .question-index > span').first()).toHaveText('第 5 题')
  await expect(livePreview.locator('.preview-question-number')).toHaveText('5、')

  await page.getByRole('tab', { name: '评价指标' }).click()
  await page.getByRole('button', { name: '增加指标' }).click()
  await page.getByLabel('指标名称').fill('协作能力')
  const weight = page.getByLabel('权重（%）')
  await expect(weight).toHaveValue('0')
  // 整数不补零，小数继续经过原有四位定点规范化，键盘步进和范围限制保持有效。
  for (const [input, displayed] of [['33.3333', '33.3333'], ['50.5000', '50.5'], ['12.34567', '12.3457'], ['-1', '0'], ['101', '100']]) {
    await weight.fill(input)
    await weight.press('Tab')
    await expect(weight).toHaveValue(displayed)
    await expect(page.locator('.weight-summary')).toContainText(`${displayed}%`)
  }
  await weight.fill('50.5')
  await weight.press('Tab')
  await expect(page.locator('.weight-summary')).toContainText('还差49.5%')
  await weight.press('ArrowUp')
  await expect(weight).toHaveValue('51.5')
  await expect(page.locator('.weight-summary')).toContainText('还差48.5%')
  await weight.fill('100')
  await weight.press('Tab')
  await expect(page.locator('.weight-summary')).toHaveClass(/el-alert--success/)
  await expect(page.locator('.weight-summary')).toContainText('权重达标')
  await page.getByRole('button', { name: '增加指标' }).click()
  const excessWeight = page.getByLabel('权重（%）').last()
  await excessWeight.fill('20.0001')
  await excessWeight.press('Tab')
  await expect(page.locator('.weight-summary')).toHaveClass(/el-alert--error/)
  await expect(page.locator('.weight-summary')).toContainText('超出20.0001%')
  const weightSummary = page.locator('.weight-summary')
  const summaryBox = await weightSummary.boundingBox()
  const summaryParts = await weightSummary.locator('.el-alert__title > *').evaluateAll(elements => elements.map(element => {
    const rect = element.getBoundingClientRect()
    return { top: rect.top, bottom: rect.bottom, right: rect.right }
  }))
  expect(Math.max(...summaryParts.map(part => part.top)) - Math.min(...summaryParts.map(part => part.top))).toBeLessThan(2)
  expect(Math.max(...summaryParts.map(part => part.right))).toBeLessThanOrEqual(summaryBox.x + summaryBox.width)
  await page.getByRole('button', { name: '删除指标 2', exact: true }).click()
  await expect(page.locator('.weight-summary')).toHaveClass(/el-alert--success/)

  await page.getByRole('button', { name: '保存草稿' }).click()
  await expect(page.getByText(/草稿已保存；仍有1项发布前检查待处理/)).toBeVisible()
  expect(saveCount).toBe(1)
  expect(persistedDraft.pages).toHaveLength(2)
  expect(persistedDraft.pages.flatMap(item => item.questions).map(item => item.questionType)).toEqual([
    'SINGLE_CHOICE',
    'STAR_RATING',
    'NUMERIC_INPUT',
    'SLIDER',
    'TEXT'
  ])
  expect(persistedDraft.indicators[0].weight).toBe('100.0000')
  expect(persistedDraft.pages[0].questions[0].options.every(option => Number.isInteger(Number(option.score)))).toBe(true)

  await page.reload()
  await expect(page.locator('.outline-page-group')).toHaveCount(2)
  await expect(page.getByRole('tab', { name: '题目属性', exact: true })).toHaveAttribute('aria-selected', 'true')
  await page.getByRole('tab', { name: '评价指标', exact: true }).click()
  await expect(page.getByLabel('权重（%）')).toHaveValue('100')
  await page.getByRole('tab', { name: '实时预览', exact: true }).click()
  await expect(page.getByRole('button', { name: /请给出一项最具体的改进建议/ })).toBeVisible()
  expect(draftReadCount).toBeGreaterThanOrEqual(2)

  await expect(page.getByRole('button', { name: '电脑 / 手机预览' })).toHaveCount(0)
  await expect(livePreview.locator('.live-preview-toolbar')).toContainText('第 1 / 2 页')
  const previewHeading = livePreview.locator('.preview-document-heading')
  await expect(previewHeading.getByRole('heading', { level: 2 })).toBeVisible()
  await expect(previewHeading).toContainText('请依据最近半年的实际协作表现作答')
  await livePreview.locator('.live-preview-pagination').getByText('2', { exact: true }).click()
  await expect(livePreview.locator('.live-preview-toolbar')).toContainText('第 2 / 2 页')
  await expect(page.locator('.question-card')).toHaveCount(1)
  await expect(page.locator('.question-card .question-index > span').first()).toHaveText('第 5 题')
  await expect(livePreview.locator('.preview-question-number')).toHaveText('5、')
  await expect(previewHeading.getByRole('heading', { level: 2 })).toBeVisible()
  await expect(previewHeading).toContainText('请依据最近半年的实际协作表现作答')
  await expect(livePreview.getByText('请给出一项最具体的改进建议', { exact: true })).toBeVisible()
  await livePreview.getByRole('textbox', { name: '问答内容' }).fill('分页试填保留')
  await livePreview.locator('.live-preview-pagination').getByText('1', { exact: true }).click()
  const slider = livePreview.getByRole('slider', { name: '滑动评分' })
  await slider.focus()
  await slider.press('ArrowRight')
  await expect(livePreview.getByText(/尚未作答/)).toHaveCount(0)
  await livePreview.locator('.live-preview-pagination').getByText('2', { exact: true }).click()
  await expect(livePreview.getByRole('textbox', { name: '问答内容' })).toHaveValue('分页试填保留')
  const hasHorizontalOverflow = await livePreview
    .locator('.preview-document')
    .evaluate(element => element.scrollWidth > element.clientWidth)
  expect(hasHorizontalOverflow).toBe(false)
  expect(saveCount).toBe(1)
})
