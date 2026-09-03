import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'

const backend = process.env.FEEDBACK_BACKEND_ROOT
  ? `${resolve(process.env.FEEDBACK_BACKEND_ROOT)}/`
  : fileURLToPath(new URL('../../../ruoyi-fastapi-backend/', import.meta.url))
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

test('真实HR发布、员工答题、HR完成关闭未交任务并保持已提交答案不可变', async ({ page }) => {
  test.setTimeout(240000)
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

  await login(page, state.partial_hr)
  await expect(page).toHaveURL(/\/hr\/projects$/)
  await page.goto(`/employee/todos/${state.project_id}`)
  await expect(page.getByText('我的进度：已提交 0/1 份')).toBeVisible()
  await page.getByRole('button', { name: '开始评价', exact: true }).first().click()
  const draftUrl = page.url()
  await page.locator('label.el-radio').filter({ hasText: '很好' }).click()
  await page.getByRole('button', { name: '下一页', exact: true }).click()
  const draftResponsePromise = page.waitForResponse(
    response => response.request().method() === 'PUT' && response.url().endsWith('/draft')
  )
  await page.getByRole('button', { name: '暂存答卷', exact: true }).click()
  const savedDraft = (await (await draftResponsePromise).json()).data
  await expect(page.getByText('答卷已暂存，可稍后继续填写')).toBeVisible()
  const draftWriteContract = {
    assignmentId: savedDraft.task.assignmentId,
    payload: {
      versionId: savedDraft.task.versionId,
      lockVersion: savedDraft.lockVersion,
      lastPageId: savedDraft.lastPageId,
      answers: savedDraft.answers.map(answer => Object.fromEntries(
        Object.entries({
          questionId: answer.questionId,
          optionId: answer.optionId,
          numericValue: answer.numericValue,
          textValue: answer.textValue,
          reason: answer.reason
        }).filter(([, value]) => value !== null && value !== undefined)
      ))
    }
  }
  const draftedDatabase = JSON.parse(
    fixture('inspect').split('\n').find(line => line.startsWith('{"projectId"'))
  )
  expect(draftedDatabase.tasks.filter(task => task.status === 'DRAFT')).toHaveLength(1)
  expect(draftedDatabase.tasks.filter(task => task.status === 'PENDING')).toHaveLength(1)
  await page.goto(`/hr/projects/${state.project_id}/progress`)
  await expect(page.getByRole('heading', { name: 'P5闭环', exact: false })).toBeVisible()
  await expect(page.locator('.kpi-card').filter({ hasText: '应完成' })).toContainText('2')
  await expect(page.getByRole('button', { name: '完成项目', exact: true })).toHaveCount(0)
  const partialCompletion = await page.evaluate(async projectId => {
    const tokenPart = document.cookie.split('; ').find(item => item.startsWith('Feedback-Token='))
    const token = decodeURIComponent(tokenPart.split('=').slice(1).join('='))
    const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
    const precheckResponse = await fetch(`/dev-api/feedback/projects/${projectId}/completion-precheck`, { headers })
    const precheck = await precheckResponse.json()
    const summary = precheck.data.summary
    const response = await fetch(`/dev-api/feedback/projects/${projectId}/complete`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        projectLockVersion: precheck.data.projectLockVersion,
        expectedSummary: {
          totalCount: summary.totalCount,
          pendingCount: summary.pendingCount,
          draftCount: summary.draftCount,
          submittedCount: summary.submittedCount,
          closedIncompleteCount: summary.closedIncompleteCount
        },
        completionReason: '部分数据范围用户不允许完成项目'
      })
    })
    return { status: response.status, body: await response.json() }
  }, state.project_id)
  expect(partialCompletion.status).toBe(403)
  expect(partialCompletion.body.data.code).toBe('PROJECT_COMPLETION_SCOPE_FORBIDDEN')
  await page.getByRole('button', { name: '退出登录', exact: true }).click()

  await login(page, state.hr)
  await expect(page).toHaveURL(/\/hr\/projects$/)
  await page.goto(`/hr/projects/${state.project_id}/progress`)
  await expect(page.getByRole('heading', { name: 'P5闭环', exact: false })).toBeVisible()
  await expect(page.locator('.kpi-card').filter({ hasText: '应完成' })).toContainText('4')
  await expect(page.locator('.kpi-card').filter({ hasText: '已提交' })).toContainText('2')
  await expect(page.locator('.kpi-card').filter({ hasText: '已暂存' })).toContainText('1')
  await expect(page.locator('.kpi-card').filter({ hasText: '未开始' })).toContainText('1')
  await page.getByRole('button', { name: '完成项目', exact: true }).click()
  const completionDrawer = page.getByRole('dialog', { name: '完成项目实时预检' })
  await expect(completionDrawer).toContainText('已提交 2')
  await expect(completionDrawer).toContainText('已暂存 1')
  await expect(completionDrawer).toContainText('未开始 1')
  await completionDrawer.getByLabel('完成原因').fill('P7真实验收：关闭未交任务并冻结已提交答卷')
  await completionDrawer.locator('label.el-checkbox').click()
  await completionDrawer.getByRole('button', { name: '确认完成项目', exact: true }).click()
  await expect(page.getByText('项目已完成', { exact: true })).toBeVisible()
  await expect(page.getByText('已完成', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '完成项目', exact: true })).toHaveCount(0)

  const completedDatabase = JSON.parse(
    fixture('inspect')
      .split('\n')
      .find(line => line.startsWith('{"projectId"'))
  )
  expect(completedDatabase.projectStatus).toBe('COMPLETED')
  expect(completedDatabase.projectCompletedBy).toBe(state.user_ids[3])
  expect(completedDatabase.projectCompletionReason).toBe('P7真实验收：关闭未交任务并冻结已提交答卷')
  expect(completedDatabase.tasks.filter(task => task.status === 'SUBMITTED')).toHaveLength(2)
  expect(completedDatabase.tasks.filter(task => task.status === 'CLOSED_INCOMPLETE')).toHaveLength(2)
  expect(
    completedDatabase.tasks.filter(task => task.status === 'CLOSED_INCOMPLETE' && task.answerCount === 1)
  ).toHaveLength(1)
  expect(completedDatabase.tasks.filter(task => task.status === 'SUBMITTED').every(task => task.answerCount === 5)).toBe(
    true
  )
  for (const beforeTask of draftedDatabase.tasks.filter(task => task.status === 'SUBMITTED')) {
    expect(completedDatabase.tasks.find(task => task.taskId === beforeTask.taskId)).toEqual(beforeTask)
  }
  const draftedTaskBeforeCompletion = draftedDatabase.tasks.find(task => task.status === 'DRAFT')
  expect(completedDatabase.tasks.find(task => task.taskId === draftedTaskBeforeCompletion.taskId).answerSheet).toEqual(
    draftedTaskBeforeCompletion.answerSheet
  )
  expect(completedDatabase.completionAudits).toEqual([
    {
      result: 'SUCCESS',
      operatorUserId: state.user_ids[3],
      beforeTotalCount: 4,
      beforeSubmittedCount: 2,
      beforeDraftCount: 1,
      beforePendingCount: 1,
      beforeClosedIncompleteCount: 0,
      closedIncompleteCount: 2,
      completionReason: 'P7真实验收：关闭未交任务并冻结已提交答卷',
      completedTime: completedDatabase.projectCompletedTime
    }
  ])

  await page.getByRole('button', { name: '退出登录', exact: true }).click()
  await login(page, state.employee)
  await expect(page).toHaveURL(/\/employee\/todos$/)
  const firstAssignmentId = new URL(firstUrl).pathname.split('/').pop()
  await page.goto(`/employee/reviews/${firstAssignmentId}`)
  await expect(page.getByText('这份评价已提交，答案不可修改。')).toBeVisible()
  await expect(page.getByPlaceholder(/原因/)).toHaveValue('第一人：主动配合')
  await page.getByRole('button', { name: '退出登录', exact: true }).click()

  await login(page, state.partial_hr)
  await expect(page).toHaveURL(/\/hr\/projects$/)
  const rejectedWrites = await page.evaluate(async contract => {
    const tokenPart = document.cookie.split('; ').find(item => item.startsWith('Feedback-Token='))
    const token = decodeURIComponent(tokenPart.split('=').slice(1).join('='))
    const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
    const baseUrl = `/dev-api/feedback/employee/tasks/${contract.assignmentId}`
    const draftResponse = await fetch(`${baseUrl}/draft`, {
      method: 'PUT', headers, body: JSON.stringify(contract.payload)
    })
    const submitResponse = await fetch(`${baseUrl}/submit`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ ...contract.payload, submissionId: crypto.randomUUID() })
    })
    return {
      draft: { status: draftResponse.status, body: await draftResponse.json() },
      submit: { status: submitResponse.status, body: await submitResponse.json() }
    }
  }, draftWriteContract)
  expect(rejectedWrites.draft.status).toBe(409)
  expect(rejectedWrites.draft.body.data.code).toBe('PROJECT_CLOSED')
  expect(rejectedWrites.submit.status).toBe(409)
  expect(rejectedWrites.submit.body.data.code).toBe('PROJECT_CLOSED')
  expect(JSON.parse(fixture('inspect').split('\n').find(line => line.startsWith('{"projectId"')))).toEqual(
    completedDatabase
  )
  await page.goto(draftUrl)
  await expect(page.getByRole('button', { name: '暂存答卷', exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '提交本份评价', exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: '退出登录', exact: true }).click()
  await expect(page).toHaveURL(/\/login$/)
  await page.goto(firstUrl)
  await expect(page).toHaveURL(/\/login\?redirect=/)
  expect(pageErrors).toEqual([])
})
