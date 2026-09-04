import { expect, test } from '@playwright/test'
import { detailFixture } from '../fixtures/answerSheet'
import { frozenDetailsFixture } from '../fixtures/frozenPublication'

async function mockWorkspace(page, context) {
  let writes = 0
  await context.addCookies([{ name: 'Feedback-Token', value: 'display-test-token', url: 'http://127.0.0.1:5176' }])
  await page.route('**/dev-api/**', route => {
    const path = new URL(route.request().url()).pathname.replace('/dev-api', '')
    if (route.request().method() !== 'GET') writes += 1
    const reply = data => route.fulfill({ json: { code: 200, data } })
    if (path === '/transport/crypto/frontend-config') return reply({
      transportCryptoEnabled: false, transportCryptoMode: 'off', transportCryptoActive: false,
      configExpireAt: Math.floor(Date.now() / 1000) + 300
    })
    if (path === '/getInfo') return route.fulfill({ json: {
      code: 200, user: { userId: 2, userName: 'display-test', nickName: '主题测试用户' },
      roles: ['feedback_hr', 'feedback_employee'], permissions: ['*:*:*']
    } })
    if (path === '/feedback/projects' || path === '/feedback/employee/projects') {
      return route.fulfill({ json: { code: 200, rows: [], total: 0, pageNum: 1, pageSize: 10 } })
    }
    if (path === '/feedback/projects/101/questionnaire-draft') return reply({
      ...frozenDetailsFixture().questionnaire, projectId: 101, projectName: '显示设置测试',
      versionStatus: 'DRAFT', projectStatus: 'PREPARING', validationIssues: [], isPublishReady: true
    })
    if (path === '/feedback/projects/101/publication-config') return reply({
      projectId: 101, projectName: '显示设置测试', projectStatus: 'ACTIVE', projectLockVersion: 1,
      versionId: 201, versionLockVersion: 1, versionStatus: 'FROZEN', editable: false,
      targets: [], relations: [], evaluatorSelections: [], configuredParticipants: [],
      preview: { targetCount: 0, evaluatorCount: 0, assignmentCount: 0, targetSummaries: [] },
      validationIssues: [], isPublishReady: true, frozenDetails: frozenDetailsFixture()
    })
    if (path === '/feedback/employee/tasks/1') return reply(detailFixture())
    return route.fulfill({ status: 404, json: { code: 404, msg: '未匹配测试接口' } })
  })
  return () => writes
}

async function expectDarkSurface(locator) {
  await expect(locator).toBeVisible()
  // Element Plus 的背景有过渡动画，等待最终配色，避免断言过渡帧。
  await expect.poll(() => locator.evaluate(element => {
    const channels = getComputedStyle(element).backgroundColor.match(/[\d.]+/g).map(Number)
    return channels.slice(0, 3).every(channel => channel < 100) && (channels[3] ?? 1) > 0.9
  })).toBe(true)
}

test('主题切换保留输入、刷新及跨工作台恢复，弹窗和下拉菜单适配暗色', async ({ page, context }) => {
  const writes = await mockWorkspace(page, context)
  await page.goto('/hr/projects')
  const search = page.getByPlaceholder('输入项目名称')
  await search.fill('尚未查询的名称')
  await page.getByRole('button', { name: '切换到深色模式', exact: true }).click()
  await expect(page.locator('html')).toHaveClass(/dark/)
  await expect(search).toHaveValue('尚未查询的名称')
  await expectDarkSurface(page.locator('.workspace-page-header'))
  await expectDarkSurface(page.locator('.el-card').first())
  await page.locator('.el-select__wrapper').first().click()
  await expectDarkSurface(page.locator('.el-popper.is-light:visible').filter({ has: page.locator('.el-select-dropdown') }))
  await page.keyboard.press('Escape')
  await page.getByRole('button', { name: '创建项目', exact: true }).click()
  await expectDarkSurface(page.getByRole('dialog', { name: '创建评价项目' }).locator('.el-dialog'))
  await page.getByRole('dialog').getByRole('textbox', { name: /项目名称/ }).fill('未保存草稿')
  await page.getByRole('dialog').getByRole('button', { name: '取消', exact: true }).click()
  await page.reload()
  await expect(page.getByRole('button', { name: '切换到浅色模式', exact: true })).toBeVisible()
  await expect(page.locator('html')).toHaveClass(/dark/)
  await page.getByRole('button', { name: '员工工作台', exact: true }).click()
  await expect(page).toHaveURL(/\/employee\/todos$/)
  await expect(page.locator('html')).toHaveClass(/dark/)
  await page.getByRole('button', { name: '用户菜单', exact: true }).click()
  await expectDarkSurface(page.locator('.el-dropdown-menu:visible'))
  await page.getByRole('button', { name: '用户菜单', exact: true }).click()
  await page.getByRole('button', { name: '切换到浅色模式', exact: true }).click()
  await expect(page.locator('html')).not.toHaveClass(/dark/)
  await expect(page.locator('.workspace-page-header')).toHaveCSS('background-color', 'rgb(255, 255, 255)')
  expect(writes()).toBe(0)
})

test('浏览器真实全屏进入、按钮退出和外部退出后状态一致', async ({ page, context }) => {
  await mockWorkspace(page, context)
  await page.goto('/hr/projects')
  await page.getByRole('button', { name: '进入全屏', exact: true }).click()
  await expect.poll(() => page.evaluate(() => Boolean(document.fullscreenElement))).toBe(true)
  await expect(page.getByRole('button', { name: '退出全屏', exact: true })).toBeEnabled()
  await page.getByRole('button', { name: '退出全屏', exact: true }).click()
  await expect.poll(() => page.evaluate(() => Boolean(document.fullscreenElement))).toBe(false)
  await page.getByRole('button', { name: '进入全屏', exact: true }).click()
  await expect.poll(() => page.evaluate(() => Boolean(document.fullscreenElement))).toBe(true)
  // 通过浏览器退出触发原生事件，覆盖按钮之外的全屏状态变化。
  await page.evaluate(() => document.exitFullscreen())
  await expect(page.getByRole('button', { name: '进入全屏', exact: true })).toBeEnabled()
})

test('问卷编辑、冻结详情及员工答题内容适配暗色且切换不丢失答案', async ({ page, context }) => {
  const writes = await mockWorkspace(page, context)
  await page.goto('/hr/projects/101/editor')
  await page.getByRole('button', { name: '切换到深色模式', exact: true }).click()
  await expectDarkSurface(page.locator('.question-card').first())
  await expectDarkSurface(page.locator('.rich-text').first())
  await expectDarkSurface(page.locator('.editor-panel').first())
  await page.goto('/hr/projects/101/publication')
  await page.getByRole('tab', { name: '问卷与指标', exact: true }).click()
  await expectDarkSurface(page.locator('.detail-tabs'))
  await expect(page.locator('.frozen-question').first()).toContainText('协作评价')
  await page.goto('/employee/tasks/1')
  await expectDarkSurface(page.locator('.answer-document'))
  await page.locator('.el-radio').filter({ hasText: '一般' }).click()
  await expect(page.getByText('已作答 1/5 题')).toBeVisible()
  await page.getByRole('button', { name: '切换到浅色模式', exact: true }).click()
  await expect(page.getByRole('radio', { name: '一般', exact: true })).toBeChecked()
  await page.getByRole('button', { name: '切换到深色模式', exact: true }).click()
  await expect(page.getByRole('radio', { name: '一般', exact: true })).toBeChecked()
  await expectDarkSurface(page.locator('.answer-footer'))
  expect(writes()).toBe(0)
})
