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
        pageDescription: '',
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

test('HR完成P4五题型、多页、指标、保存重载和手机预览', async ({ page }) => {
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
  await page.locator('.tiptap').fill('请依据最近半年的实际协作表现作答')

  for (const label of ['单选题', '星级评分', '数字输入', '滑动评分']) {
    await page.getByRole('button', { name: new RegExp(`^${label}`) }).click()
  }
  await expect(page.locator('.question-card')).toHaveCount(4)

  await page.getByRole('button', { name: '增加页面' }).click()
  await page.getByRole('button', { name: /^问答题/ }).click()
  await page.getByLabel('题目标题').fill('请给出一项最具体的改进建议')
  await expect(page.locator('.question-card')).toHaveCount(1)

  await page.getByRole('tab', { name: '评价指标' }).click()
  await page.getByRole('button', { name: '增加指标' }).click()
  await page.getByLabel('指标名称').fill('协作能力')
  await page.getByLabel('权重（%）').fill('100')

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

  await page.reload()
  await expect(page.locator('.outline-page-group')).toHaveCount(2)
  await expect(page.getByRole('button', { name: /请给出一项最具体的改进建议/ })).toBeVisible()
  expect(draftReadCount).toBeGreaterThanOrEqual(2)

  await page.getByRole('button', { name: '电脑 / 手机预览' }).click()
  const previewDialog = page.getByRole('dialog', { name: '问卷预览' })
  await previewDialog.getByText('手机', { exact: true }).click()
  await expect(previewDialog.getByText('1. 第1页')).toBeVisible()
  await expect(previewDialog.getByText('2. 第2页')).toBeVisible()
  const slider = previewDialog.getByRole('slider', { name: '滑动评分' })
  await slider.focus()
  await slider.press('ArrowRight')
  await expect(previewDialog.getByText(/尚未作答/)).toHaveCount(0)
  const hasHorizontalOverflow = await previewDialog
    .locator('.preview-stage')
    .evaluate(element => element.scrollWidth > element.clientWidth)
  expect(hasHorizontalOverflow).toBe(false)
  expect(saveCount).toBe(1)
})
