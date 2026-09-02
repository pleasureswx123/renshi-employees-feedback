import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'

const backend = fileURLToPath(new URL('../../../ruoyi-fastapi-backend/', import.meta.url))
const python = `${backend}${process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python'}`
const statePath = `${backend}.tmp/p6-live-automated.json`
let state

function fixture(action) {
  return execFileSync(python, ['scripts/feedback_p6_e2e_fixture.py', action, '--state', statePath], {
    cwd: backend, encoding: 'utf8', timeout: 60000
  })
}

async function login(page, account) {
  const captcha = page.waitForResponse(response => response.url().endsWith('/captchaImage'))
  await page.goto('/login')
  await captcha
  await page.getByLabel('账号').fill(account)
  await page.getByLabel('密码', { exact: false }).fill(state.password)
  await page.getByRole('button', { name: '登录', exact: true }).click()
}

async function fillFirstPage(page, reason) {
  await page.locator('label.el-radio').filter({ hasText: '很好' }).click()
  await page.getByPlaceholder(/原因/).fill(reason)
  const stars = page.locator('.el-rate')
  await stars.focus()
  // 此冻结夹具允许0至5：第5颗星对应实际4分。
  await stars.press('Home')
  await stars.press('ArrowRight')
  await stars.press('ArrowRight')
  await stars.press('ArrowRight')
  await stars.press('ArrowRight')
  await stars.press('ArrowRight')
  await expect(stars).toContainText('4 分')
}

async function fillSecondPage(page, text) {
  await page.getByRole('button', { name: '下一页', exact: true }).click()
  const visiblePage = page.locator('.answer-page:visible')
  await visiblePage.locator('.el-input-number input').first().fill('42.25')
  await visiblePage.locator('.el-input-number input').first().press('Tab')
  await visiblePage.locator('.el-slider__input input').fill('4.5')
  await visiblePage.locator('.el-slider__input input').press('Tab')
  await visiblePage.locator('textarea').fill(text)
}

async function confirmSubmit(page) {
  await page.getByRole('button', { name: '提交本份评价', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '确认提交本份评价' })
  await expect(dialog).toContainText('提交后不能修改')
  await dialog.getByRole('button', { name: '确认提交', exact: true }).click()
  await expect(page.getByText('这份评价已提交，答案不可修改。')).toBeVisible()
  await expect(page.getByRole('button', { name: '提交本份评价', exact: true })).toHaveCount(0)
}

test.beforeAll(() => {
  fixture('prepare')
  state = JSON.parse(readFileSync(statePath, 'utf8'))
})

test.afterAll(() => {
  if (state) fixture('cleanup')
})

test('真实HR发布、员工两人独立暂存提交、恢复、历史与数据库对账', async ({ page }) => {
  // 不拦截业务接口：使用完整RuoYi登录和真实PostgreSQL持久化。
  const pageErrors = []
  page.on('pageerror', error => pageErrors.push(error.message))
  await login(page, state.hr)
  await expect(page).toHaveURL(/\/hr\/projects$/)
  await page.goto(`/hr/projects/${state.project_id}/publication`)
  await page.getByRole('button', { name: '发布项目', exact: true }).click()
  const publishDialog = page.getByRole('dialog', { name: '确认发布项目' })
  await expect(publishDialog).toContainText('生成4项任务')
  await publishDialog.getByRole('button', { name: '确认发布', exact: true }).click()
  await expect(page.getByText('已冻结只读')).toBeVisible()
  await page.getByRole('button', { name: '退出登录', exact: true }).click()

  await login(page, state.employee)
  await expect(page).toHaveURL(/\/employee\/todos$/)
  await expect(page.getByRole('button', { name: 'HR 工作台' })).toHaveCount(0)
  await page.goto(`/employee/todos/${state.project_id}`)
  await expect(page.getByText('我的进度：已提交 0/2 份')).toBeVisible()
  await page.getByRole('button', { name: '开始评价', exact: true }).first().click()
  await expect(page.getByRole('heading', { name: 'P6五题型问卷' })).toBeVisible()
  const firstUrl = page.url()
  await page.locator('label.el-radio').filter({ hasText: '很好' }).click()
  await page.getByRole('button', { name: '下一页', exact: true }).click()
  await page.getByRole('button', { name: '暂存答卷', exact: true }).click()
  await expect(page.getByText('答卷已暂存，可稍后继续填写')).toBeVisible()
  await page.reload()
  await expect(page.getByRole('heading', { name: '质量与建议', exact: true })).toBeVisible()
  await expect(page.locator('.answer-page:visible .el-input-number input').first()).toHaveValue('')
  await expect(page.getByText('已作答 1/5 题')).toBeVisible()
  await page.getByRole('button', { name: '提交本份评价', exact: true }).click()
  await expect(page.getByRole('heading', { name: '协作表现', exact: true })).toBeVisible()
  await expect(page.getByRole('dialog', { name: '确认提交本份评价' })).toHaveCount(0)
  await expect(page.getByRole('radio', { name: /很好/ })).toBeChecked()
  await fillFirstPage(page, '第一人：主动配合')
  await fillSecondPage(page, '第一人的独立建议')
  await expect(page.locator('.el-form-item__error')).toHaveCount(0)
  await expect(page.getByText('请检查以下题目')).toHaveCount(0)
  await page.setViewportSize({ width: 390, height: 844 })
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.screenshot({ path: '../output/playwright/p6-answer-mobile.png', fullPage: true })
  await confirmSubmit(page)
  await page.getByRole('button', { name: '继续处理其他任务', exact: true }).click()
  await expect(page.getByText('我的进度：已提交 1/2 份')).toBeVisible()
  await page.getByRole('button', { name: '开始评价', exact: true }).click()
  expect(page.url()).not.toBe(firstUrl)
  await expect(page.getByText('已作答 0/5 题')).toBeVisible()
  await fillFirstPage(page, '第二人：主动配合')
  await fillSecondPage(page, '第二人的独立建议')
  await confirmSubmit(page)
  await page.getByRole('button', { name: '继续处理其他任务', exact: true }).click()
  await expect(page.getByText('我的进度：已提交 2/2 份')).toBeVisible()
  await page.getByRole('button', { name: '查看答案', exact: true }).first().click()
  await expect(page.getByText('这份评价已提交，答案不可修改。')).toBeVisible()
  await expect(page.getByPlaceholder(/原因/)).toHaveValue('第一人：主动配合')
  await expect(page.getByPlaceholder(/原因/)).toHaveAttribute('readonly', '')
  await page.reload()
  await expect(page.getByText('这份评价已提交，答案不可修改。')).toBeVisible()
  await page.getByRole('button', { name: '返回我评价的', exact: true }).click()
  await expect(page.locator('.employee-task-card')).toHaveCount(2)
  await page.goto('/hr/projects')
  await expect(page).toHaveURL(/\/403$/)
  const database = JSON.parse(fixture('inspect').split(/\r?\n/).find(line => line.startsWith('{"projectId"')))
  expect(database.projectStatus).toBe('ACTIVE')
  const submitted = database.tasks.filter(task => task.status === 'SUBMITTED')
  expect(submitted).toHaveLength(2)
  expect(submitted.every(task => task.answerCount === 5 && task.rawScore === '53.7500')).toBe(true)
  expect(database.tasks.filter(task => task.status === 'PENDING')).toHaveLength(2)
  await page.goto('/employee/todos')
  await expect(page.getByText('暂无待处理的评价任务')).toBeVisible()
  await page.getByRole('button', { name: '退出登录', exact: true }).click()
  await expect(page).toHaveURL(/\/login$/)
  await page.goto(firstUrl)
  await expect(page).toHaveURL(/\/login\?redirect=/)
  expect(pageErrors).toEqual([])
})
