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
  await expect(page).toHaveURL(/\/employee\/todos$/)
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
  await page.getByRole('button', { name: '用户菜单', exact: true }).click()
  await page.getByRole('menuitem', { name: '退出登录', exact: true }).click()

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
  await expect(page.locator('.page-navigation')).toContainText('2/2')
  await expect(page.locator('.answer-page:visible .answer-question-heading').first()).toContainText('第 3 题：')
  await expect(page.locator('.answer-page:visible .el-input-number input').first()).toHaveValue('')
  await expect(page.getByText('已作答 1/5 题')).toBeVisible()
  await page.getByRole('button', { name: '提交本份评价', exact: true }).click()
  await expect(page.locator('.page-navigation')).toContainText('1/2')
  await expect(page.locator('.answer-page:visible .answer-question-heading').first()).toContainText('第 1 题：')
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
  await page.goto(`/employee/todos/${state.project_id}`)
  await expect(page.getByText('我的进度：已提交 1/2 份')).toBeVisible()
  await page.getByRole('button', { name: '开始评价', exact: true }).click()
  expect(page.url()).not.toBe(firstUrl)
  await expect(page.getByText('已作答 0/5 题')).toBeVisible()
  await fillFirstPage(page, '第二人：主动配合')
  await fillSecondPage(page, '第二人的独立建议')
  await confirmSubmit(page)
  await page.goto(`/employee/todos/${state.project_id}`)
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
  await page.getByRole('button', { name: '用户菜单', exact: true }).click()
  await page.getByRole('menuitem', { name: '退出登录', exact: true }).click()

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
  await page.getByRole('button', { name: '用户菜单', exact: true }).click()
  await page.getByRole('menuitem', { name: '退出登录', exact: true }).click()

  await login(page, state.hr)
  await expect(page).toHaveURL(/\/hr\/projects$/)
  await page.goto(`/hr/projects/${state.project_id}/progress`)
  await expect(page.getByRole('heading', { name: 'P5闭环', exact: false })).toBeVisible()
  await expect(page.locator('.kpi-card').filter({ hasText: '应完成' })).toContainText('4')
  await expect(page.locator('.kpi-card').filter({ hasText: '已提交' })).toContainText('2')
  await expect(page.locator('.kpi-card').filter({ hasText: '已暂存' })).toContainText('1')
  await expect(page.locator('.kpi-card').filter({ hasText: '未开始' })).toContainText('1')
  await page.getByRole('button', { name: '提前结束', exact: true }).click()
  const completionDrawer = page.getByRole('dialog', { name: '提前结束项目确认' })
  await expect(completionDrawer).toContainText('已提交 2')
  await expect(completionDrawer).toContainText('已暂存 1')
  await expect(completionDrawer).toContainText('未开始 1')
  await completionDrawer.getByLabel('完成原因').fill('P7真实验收：关闭未交任务并冻结已提交答卷')
  await completionDrawer.locator('label.el-checkbox').click()
  await completionDrawer.getByRole('button', { name: '确认提前结束', exact: true }).click()
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

  await page.getByRole('button', { name: '用户菜单', exact: true }).click()
  await page.getByRole('menuitem', { name: '退出登录', exact: true }).click()
  await login(page, state.employee)
  await expect(page).toHaveURL(/\/employee\/todos$/)
  const firstAssignmentId = new URL(firstUrl).pathname.split('/').pop()
  await page.goto(`/employee/reviews/${firstAssignmentId}`)
  await expect(page.getByText('这份评价已提交，答案不可修改。')).toBeVisible()
  await expect(page.getByPlaceholder(/原因/)).toHaveValue('第一人：主动配合')
  await page.getByRole('button', { name: '用户菜单', exact: true }).click()
  await page.getByRole('menuitem', { name: '退出登录', exact: true }).click()

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
  await page.getByRole('button', { name: '用户菜单', exact: true }).click()
  await page.getByRole('menuitem', { name: '退出登录', exact: true }).click()
  await expect(page).toHaveURL(/\/login$/)
  await page.goto(firstUrl)
  await expect(page).toHaveURL(/\/login\?redirect=/)

  // P8：完成后从HR进度入口生成报告，与真实数据库和手算对账。
  await page.setViewportSize({ width: 1440, height: 1000 })
  await login(page, state.hr)
  await expect(page).toHaveURL(/\/hr\/projects$/)
  await page.goto(`/hr/projects/${state.project_id}/progress`)
  await page.getByRole('button', { name: '查看报告', exact: true }).click()
  await expect(page.getByRole('heading', { name: '团队排名与明细' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '团队排名与明细' })).toBeVisible()
  await expect(page.locator('.el-table__body-wrapper').first()).toContainText('45.55')
  await expect(page.locator('.summary')).toContainText('50.00%')
  await page.reload()
  await expect(page.getByRole('heading', { name: '团队排名与明细' })).toBeVisible()
  await expect(page.getByRole('button', { name: '生成报告', exact: true })).toHaveCount(0)
  await page.screenshot({ path: '../output/playwright/p8-team-report.png', fullPage: true, animations: 'disabled' })
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.screenshot({ path: '../output/playwright/p8-team-report-mobile.png', fullPage: true, animations: 'disabled' })
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.getByRole('button', { name: '查看得分详情', exact: true }).first().click()
  const reportDrawer = page.getByRole('dialog', { name: '得分详情', exact: true })
  await expect(reportDrawer.getByRole('heading', { name: '题目明细', exact: true })).toBeVisible()
  await expect(reportDrawer).toContainText('缺失关系')
  await expect(reportDrawer).toContainText('45.55')
  await expect(reportDrawer).not.toContainText('第一人：主动配合')
  await page.screenshot({ path: '../output/playwright/p8-person-report.png', fullPage: true, animations: 'disabled' })
  await reportDrawer.locator('.el-drawer__close-btn').click()
  const scoredDatabase = JSON.parse(fixture('inspect').split('\n').find(line => line.startsWith('{"projectId"')))
  const totals = scoredDatabase.scoreResults.filter(row => row.resultType === 'PERSON_TOTAL')
  expect(totals).toHaveLength(2)
  expect(totals.every(row => row.score.startsWith('45.550847457627118644') && row.calculationVersion === 'feedback-score-v1')).toBe(true)
  expect(scoredDatabase.tasks).toEqual(completedDatabase.tasks)
  await page.getByRole('button', { name: '已提交答卷', exact: true }).click()
  await page.getByRole('button', { name: '查看答卷', exact: true }).first().click()
  const answerDrawer = page.getByRole('dialog', { name: '已提交答卷', exact: true })
  await expect(answerDrawer).toContainText('已提交，只读')
  await expect(answerDrawer.getByPlaceholder(/原因/)).toHaveValue('第一人：主动配合')
  await answerDrawer.locator('.el-drawer__close-btn').click()
  await page.getByRole('button', { name: '用户菜单', exact: true }).click()
  await page.getByRole('menuitem', { name: '退出登录', exact: true }).click()

  await login(page, state.report_hr)
  await expect(page).toHaveURL(/\/hr\/reports$/)
  await page.getByRole('button', { name: '查看报告', exact: true }).first().click()
  await expect(page.getByRole('heading', { name: '团队排名与明细' })).toBeVisible()
  await expect(page.getByRole('button', { name: '已提交答卷', exact: true })).toHaveCount(0)
  const deniedAnswers = await page.evaluate(async id => {
    const part = document.cookie.split('; ').find(item => item.startsWith('Feedback-Token='))
    const token = decodeURIComponent(part.split('=').slice(1).join('='))
    return (await (await fetch(`/dev-api/feedback/projects/${id}/answers`, { headers: { Authorization: `Bearer ${token}` } })).json()).code
  }, state.project_id)
  expect(deniedAnswers).toBe(403)
  await page.getByRole('button', { name: '用户菜单', exact: true }).click()
  await page.getByRole('menuitem', { name: '退出登录', exact: true }).click()

  await login(page, state.partial_hr)
  await expect(page).toHaveURL(/\/hr\/projects$/)
  await page.goto(`/hr/projects/${state.project_id}/reports`)
  await expect(page.getByText('当前数据范围仅覆盖部分被评价人，排名和统计仅限可见范围')).toBeVisible()
  await expect(page.getByRole('button', { name: '查看得分详情', exact: true })).toHaveCount(1)
  await expect(page.locator('.summary')).toContainText('1 / 2')
  await page.getByRole('button', { name: '用户菜单', exact: true }).click()
  await page.getByRole('menuitem', { name: '退出登录', exact: true }).click()
  expect(pageErrors).toEqual([])
})

async function realApi(page, method, path, body) {
  return page.evaluate(async ({ method, path, body }) => {
    const part = document.cookie.split('; ').find(item => item.startsWith('Feedback-Token='))
    const token = decodeURIComponent(part.split('=').slice(1).join('='))
    const response = await fetch(`/dev-api${path}`, {
      method, headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body)
    })
    return { status: response.status, body: await response.json(), requestId: response.headers.get('request-id') }
  }, { method, path, body })
}

test('P9真实创建项目、跨用户拒绝及下级不适用和缺失关系报告验收', async ({ page }) => {
  test.setTimeout(180000)
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  await page.setViewportSize({ width: 1440, height: 1000 })
  await login(page, state.hr)
  await expect(page).toHaveURL(/\/hr\/projects$/)
  const health = await realApi(page, 'GET', '/feedback/health')
  expect(health.body.data).toMatchObject({ status: 'ready', phase: 'P9', schemaRevision: '20260903_08_feedback_scoring' })
  await page.getByRole('button', { name: '创建项目', exact: true }).click()
  const createDialog = page.getByRole('dialog', { name: '创建评价项目' })
  await createDialog.getByLabel('项目名称', { exact: true }).fill(`P9验收-${state.user_ids[3]}`)
  await createDialog.getByRole('button', { name: '创建并编辑问卷' }).click()
  await expect(page).toHaveURL(/\/hr\/projects\/\d+\/editor$/)
  const projectId = Number(new URL(page.url()).pathname.split('/')[3])
  const base = `/feedback/projects/${projectId}`
  const draft = (await realApi(page, 'GET', `${base}/questionnaire-draft`)).body.data
  // 配置通过真实鉴权HTTP持久化；五题型编辑交互沿用独立组件和既有浏览器门禁。
  const saved = await realApi(page, 'PUT', `${base}/questionnaire-draft`, {
    versionId: draft.versionId, lockVersion: draft.lockVersion, title: 'P9关系缺失验收',
    pages: [{ pageCode: 'P_MAIN', pageTitle: '评价', sortOrder: 1, questions: [
      { questionCode: 'Q_SCORE', questionType: 'NUMERIC_INPUT', title: '完成质量', isRequired: true, isScored: true, minScore: '0', maxScore: '100', decimalPlaces: 0, config: {}, options: [], sortOrder: 1 },
      { questionCode: 'Q_TEXT', questionType: 'TEXT', title: '具体建议', isRequired: true, isScored: false, config: { maxLength: 100 }, options: [], sortOrder: 2 }
    ] }],
    indicators: [{ indicatorCode: 'I_ALL', indicatorName: '综合表现', weight: '100', sortOrder: 1, questionCodes: ['Q_SCORE'] }]
  })
  expect(saved.body.code).toBe(200)
  const config = (await realApi(page, 'GET', `${base}/publication-config`)).body.data
  const relations = config.relations.map(relation => {
    const value = Object.fromEntries(['relationCode', 'relationType', 'relationName', 'isEnabled', 'participatesInScore', 'weight', 'sortOrder'].map(key => [key, relation[key]]))
    if (['REL_PEER', 'REL_SUBORDINATE'].includes(value.relationCode)) Object.assign(value, { isEnabled: true, participatesInScore: true, weight: '50' })
    return value
  })
  const configured = await realApi(page, 'PUT', `${base}/publication-config`, {
    projectLockVersion: config.projectLockVersion, versionId: config.versionId, versionLockVersion: config.versionLockVersion,
    targets: [state.user_ids[0], state.user_ids[2]].map(targetUserId => ({ targetUserId })), relations,
    evaluatorSelections: [
      ...[state.user_ids[0], state.user_ids[2]].map(targetUserId => ({ targetUserId, relationCode: 'REL_PEER', evaluatorUserIds: [state.user_ids[1]] })),
      { targetUserId: state.user_ids[2], relationCode: 'REL_SUBORDINATE', evaluatorUserIds: [state.user_ids[1]] }
    ]
  })
  expect(configured.body.code).toBe(200)
  await page.goto(`/hr/projects/${projectId}/publication`)
  await page.getByRole('button', { name: '发布项目', exact: true }).click()
  const publishDialog = page.getByRole('dialog', { name: '确认发布项目' })
  await expect(publishDialog).toContainText('生成5项任务')
  await publishDialog.getByRole('button', { name: '确认发布', exact: true }).click()
  await expect(page.getByText('已冻结只读')).toBeVisible()
  const progress = (await realApi(page, 'GET', `${base}/progress`)).body.data
  const foreignTask = progress.rows.find(row => row.evaluatorUserId === state.user_ids[0]).assignmentId
  await page.getByRole('button', { name: '用户菜单', exact: true }).click()
  await page.getByRole('menuitem', { name: '退出登录', exact: true }).click()

  await login(page, state.employee)
  await expect(page).toHaveURL(/\/employee\/todos$/)
  expect((await realApi(page, 'GET', `/feedback/employee/tasks/${foreignTask}`)).status).toBe(404)
  expect((await realApi(page, 'GET', `${base}/publication-config`)).body.code).toBe(403)
  const injected = await realApi(page, 'GET', `/feedback/employee/projects?evaluatorUserId=${state.user_ids[0]}`)
  expect(injected.status).toBe(422)
  expect(injected.body.data.code).toBe('VALIDATION_ERROR')
  for (let index = 0; index < 2; index += 1) {
    await page.goto(`/employee/todos/${projectId}`)
    const peer = page.locator('.employee-task-card').filter({ hasText: '同级评价' }).filter({ has: page.getByRole('button', { name: '开始评价', exact: true }) }).first()
    await peer.getByRole('button', { name: '开始评价', exact: true }).click()
    await page.locator('.el-input-number input').fill('80')
    await page.locator('.el-input-number input').press('Tab')
    await page.locator('.answer-page textarea').fill('P9仅原始答案权限可见的建议')
    await confirmSubmit(page)
  }
  await page.getByRole('button', { name: '用户菜单', exact: true }).click()
  await page.getByRole('menuitem', { name: '退出登录', exact: true }).click()
  await login(page, state.hr)
  await expect(page).toHaveURL(/\/hr\/projects$/)
  await page.goto(`/hr/projects/${projectId}/progress`)
  await page.getByRole('button', { name: '提前结束', exact: true }).click()
  const completion = page.getByRole('dialog', { name: '提前结束项目确认' })
  await completion.getByLabel('完成原因').fill('P9验收：保留不适用与缺失关系区别')
  await completion.locator('label.el-checkbox').click()
  await completion.getByRole('button', { name: '确认提前结束', exact: true }).click()
  await expect(page.getByText('项目已完成', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '查看报告', exact: true }).click()
  await expect(page.getByRole('heading', { name: '团队排名与明细' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '团队排名与明细' })).toBeVisible()
  await expect(page.locator('.summary')).toContainText('2 / 5')
  await expect(page.getByRole('button', { name: /导出|下载|Excel|CSV/ })).toHaveCount(0)
  const reports = []
  for (const targetUserId of [state.user_ids[0], state.user_ids[2]]) {
    const response = await realApi(page, 'GET', `${base}/reports/${targetUserId}`)
    expect(response.body.code).toBe(200)
    expect(response.requestId).toBeTruthy()
    expect(JSON.stringify(response.body)).not.toContain('P9仅原始答案权限可见的建议')
    reports.push(response.body.data)
  }
  expect(reports.map(report => report.expectedCount)).toEqual([2, 3])
  expect(reports.map(report => report.score)).toEqual(['80.00', '80.00'])
  const subordinate = reports.map(report => report.indicators[0].relations.find(row => row.relationType === 'SUBORDINATE'))
  expect(subordinate.map(row => row.status)).toEqual(['NOT_APPLICABLE', 'MISSING'])
  for (const report of reports) {
    const peer = report.indicators[0].relations.find(row => row.relationType === 'PEER')
    expect(peer.originalWeight).toBe('50.00')
    expect(peer.effectiveWeight).toBe('100.00')
  }
  await page.getByRole('button', { name: '查看得分详情', exact: true }).first().click()
  const drawer = page.getByRole('dialog', { name: '得分详情', exact: true })
  await expect(drawer).toContainText('不适用')
  await page.screenshot({ path: '../output/playwright/p9-not-applicable-report.png', fullPage: true, animations: 'disabled' })
  await drawer.locator('.el-drawer__close-btn').click()
  await page.getByRole('button', { name: '查看得分详情', exact: true }).nth(1).click()
  const missingRelation = drawer.getByRole('row', { name: /^下级 缺失关系/ })
  await expect(missingRelation.getByRole('cell', { name: '50.00', exact: true })).toBeVisible()
  await expect(missingRelation.getByRole('cell', { name: '0.00', exact: true })).toBeVisible()
  await page.screenshot({ path: '../output/playwright/p9-missing-relation-report.png', fullPage: true, animations: 'disabled' })
  await expect.poll(() => {
    const audit = JSON.parse(fixture('inspect').split(/\r?\n/).find(line => line.startsWith('{"projectId"'))).operationAudit
    expect(audit.sensitiveDataAbsent).toBe(true)
    return audit.successfulTitles
  }, { timeout: 15000 }).toEqual(expect.arrayContaining(['评价项目发布', '评价答卷提交', '评价项目完成', '评价报告生成', '已提交评价原始答案']))
  expect(errors).toEqual([])
})
