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
    settings: {},
    pages: [{ pageId: 301, pageTitle: '第1页', pageDescription: '', sortOrder: 1, questions: [] }]
  }
}

test('HR创建项目后编辑、保存、重载并完成手机预览', async ({ page }) => {
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
    route.fulfill({ json: { code: 200, token: 'p3-e2e-token' } })
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
      persistedDraft = {
        ...persistedDraft,
        ...payload,
        lockVersion: payload.lockVersion + 1,
        pages: payload.pages.map(pageItem => ({
          ...pageItem,
          pageId: pageItem.pageId || 301,
          questions: pageItem.questions.map((question, questionIndex) => ({
            ...question,
            questionId: question.questionId || 400 + questionIndex,
            options: question.options.map((option, optionIndex) => ({
              ...option,
              optionId: option.optionId || 500 + optionIndex
            }))
          }))
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
  await projectDialog.getByLabel('项目说明').fill('验证P3单选题垂直切片')
  await projectDialog.getByRole('button', { name: '创建并编辑问卷' }).click()

  await expect(page).toHaveURL(/\/hr\/projects\/101\/editor$/)
  await expect(page.getByRole('heading', { name: '问卷编辑器' })).toBeVisible()
  await page.getByRole('button', { name: /单选题/ }).click()
  await page.getByLabel('题目标题').fill('能够清晰说明团队目标')

  await page.getByRole('button', { name: '批量增加' }).click()
  const batchDialog = page.getByRole('dialog', { name: '批量增加选项' })
  await batchDialog.locator('textarea').fill('非常符合 | 5\n比较符合 | 4\n一般 | 3')
  await batchDialog.getByRole('button', { name: '应用选项' }).click()
  await page.locator('.option-editor').first().locator('.el-switch').click()

  await page.getByRole('button', { name: '复制题目' }).click()
  await expect(page.locator('.question-card')).toHaveCount(2)
  await page.getByRole('button', { name: '上移' }).click()
  await expect(page.locator('.question-card').first()).toContainText('副本')
  await page.getByRole('button', { name: '下移' }).click()
  await page.getByRole('button', { name: '删除题目' }).click()
  await page.getByRole('button', { name: '删除题目' }).last().click()
  await expect(page.locator('.question-card')).toHaveCount(1)

  await page.getByRole('button', { name: '保存草稿' }).click()
  await expect(page.getByText('问卷草稿已保存到 PostgreSQL')).toBeVisible()
  expect(saveCount).toBe(1)

  await page.reload()
  await expect(
    page.locator('.question-card').getByText('能够清晰说明团队目标', { exact: true })
  ).toBeVisible()
  await expect(page.locator('.option-editor input').first()).toHaveValue('非常符合')
  expect(draftReadCount).toBeGreaterThanOrEqual(2)

  await page.getByRole('button', { name: '电脑 / 手机预览' }).click()
  const previewDialog = page.getByRole('dialog', { name: '问卷预览' })
  await previewDialog.getByText('手机', { exact: true }).click()
  await previewDialog.getByText('非常符合', { exact: true }).click()
  await previewDialog.getByLabel('附加原因').fill('目标说明包含明确的时间和结果要求')
  const hasHorizontalOverflow = await previewDialog
    .locator('.preview-stage')
    .evaluate(element => element.scrollWidth > element.clientWidth)
  expect(hasHorizontalOverflow).toBe(false)
  expect(saveCount).toBe(1)
})
