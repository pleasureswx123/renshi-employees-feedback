import { expect, test } from '@playwright/test'
import { frozenDetailsFixture } from '../fixtures/frozenPublication'

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
    'feedback:questionnaire:edit',
    'feedback:participant:manage',
    'feedback:project:publish'
  ]
}

const candidates = [
  { userId: 10, userName: 'zhangsan', nickName: '张三', deptId: 100, deptName: '研发部', available: true },
  { userId: 11, userName: 'lisi', nickName: '李四', deptId: 100, deptName: '研发部', available: true }
]

function relation(relationId, relationCode, relationType, relationName, sortOrder, overrides = {}) {
  return {
    relationId,
    relationCode,
    relationType,
    relationName,
    isEnabled: false,
    participatesInScore: false,
    weight: '0.0000',
    sortOrder,
    fixed: true,
    ...overrides
  }
}

function initialConfig() {
  return {
    projectId: 101,
    projectName: 'P5浏览器验收项目',
    projectStatus: 'PREPARING',
    projectLockVersion: 1,
    versionId: 201,
    versionLockVersion: 1,
    versionStatus: 'DRAFT',
    editable: true,
    targets: [],
    relations: [
      relation(1, 'REL_SUPERVISOR', 'SUPERVISOR', '上级', 1),
      relation(2, 'REL_PEER', 'PEER', '同级', 2),
      relation(3, 'REL_SUBORDINATE', 'SUBORDINATE', '下级', 3),
      relation(4, 'REL_SELF', 'SELF', '自己', 4, { isEnabled: true }),
      relation(5, 'REL_OTHER', 'OTHER', '其他', 5)
    ],
    evaluatorSelections: [],
    configuredParticipants: [],
    preview: { targetCount: 0, evaluatorCount: 0, assignmentCount: 0, targetSummaries: [] },
    validationIssues: [{ code: 'TARGET_REQUIRED', path: 'targets', message: '至少选择一名被评价人' }],
    isPublishReady: false
  }
}

function readyConfig() {
  const config = initialConfig()
  return {
    ...config,
    targets: [{ ...candidates[0], targetId: 301, onlySelfEvaluation: false }],
    relations: config.relations.map(item =>
      item.relationCode === 'REL_PEER'
        ? { ...item, isEnabled: true, participatesInScore: true, weight: '100.0000' }
        : item
    ),
    evaluatorSelections: [
      { targetUserId: 10, relationCode: 'REL_PEER', evaluatorUserIds: [11], systemManaged: false },
      { targetUserId: 10, relationCode: 'REL_SELF', evaluatorUserIds: [10], systemManaged: true }
    ],
    configuredParticipants: candidates,
    preview: {
      targetCount: 1,
      evaluatorCount: 2,
      assignmentCount: 2,
      targetSummaries: [{ targetUserId: 10, selfCount: 1, nonSelfCount: 1, assignmentCount: 2 }]
    },
    validationIssues: [],
    isPublishReady: true
  }
}

async function openPublicationWithPermissions(page, permissions, config) {
  let candidateRequestCount = 0
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
    route.fulfill({ json: { code: 200, token: 'permission-token' } })
  )
  await page.route('**/dev-api/getInfo', route =>
    route.fulfill({ json: { ...userInfo, permissions } })
  )
  const handleFeedbackApi = route => {
    const request = route.request()
    const path = new URL(request.url()).pathname.replace('/dev-api', '')
    if (path === '/feedback/projects') {
      return route.fulfill({
        json: {
          code: 200,
          rows: [{ projectId: 101, projectName: '权限测试项目', status: config.projectStatus, lockVersion: 1 }],
          pageNum: 1,
          pageSize: 10,
          total: 1,
          hasNext: false
        }
      })
    }
    if (path === '/feedback/projects/101/publication-config') {
      return route.fulfill({ json: { code: 200, data: config } })
    }
    if (path === '/feedback/projects/101/participant-options') {
      candidateRequestCount += 1
      return route.fulfill({ json: { code: 200, rows: candidates, pageNum: 1, pageSize: 10, total: 2, hasNext: false } })
    }
    return route.fulfill({ status: 404, json: { code: 404, msg: '未匹配测试接口' } })
  }
  await page.route('**/dev-api/feedback/projects*', handleFeedbackApi)
  await page.route('**/dev-api/feedback/projects/**', handleFeedbackApi)

  await page.goto('/login')
  await page.getByLabel('账号').fill('permission-user')
  await page.getByLabel('密码').fill('secret')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL(/\/hr\/projects$/)
  await page.getByRole('button', { name: config.editable ? '配置并发布' : '查看发布配置' }).click()
  await expect(page.getByRole('heading', { name: config.editable ? '人员关系与发布' : '发布详情' })).toBeVisible()
  return () => candidateRequestCount
}

test('发布详情完整展示冻结问卷和人员，支持跨页定位且不加载当前人员目录', async ({ page }) => {
  await page.setViewportSize({ width: 1698, height: 986 })
  const config = { ...readyConfig(), editable: false, projectStatus: 'ACTIVE', versionStatus: 'FROZEN', frozenDetails: frozenDetailsFixture() }
  config.configuredParticipants = config.configuredParticipants.map(person => ({ ...person, nickName: `发布时${person.nickName}`, deptName: '发布时部门' }))
  let writes = 0
  page.on('request', request => { if (request.url().includes('/feedback/') && request.method() !== 'GET') writes += 1 })
  const candidateCount = await openPublicationWithPermissions(page, userInfo.permissions, config)
  await expect(page.getByText('2026-09-04 15:49:14', { exact: true })).toBeVisible()
  await expect(page.getByText('feedback-hr', { exact: true })).toBeVisible()
  await expect(page.getByText('可以发布', { exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '保存配置', exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '查看评价进度' })).toHaveCount(0)
  await page.screenshot({ path: 'output/playwright/publication-details-overview.png', fullPage: true })
  await page.getByRole('tab', { name: '问卷与指标' }).click()
  await expect(page.locator('.frozen-questionnaire')).toContainText('表现很好')
  await expect(page.locator('.frozen-indicators')).toContainText('70%')
  await page.getByRole('button', { name: '第 3 题 · 目标达成', exact: true }).click()
  await expect(page.locator('.highlighted')).toContainText('目标达成')
  await expect(page.locator('.highlighted')).toBeFocused()
  await expect(page.locator('.frozen-questionnaire')).toContainText('其他建议')
  await expect(page.locator('.frozen-questionnaire')).toContainText('默认 50.5 分')
  await expect(page.locator('.frozen-questionnaire input, .frozen-questionnaire textarea')).toHaveCount(0)
  await page.screenshot({ path: 'output/playwright/publication-details-questionnaire.png', fullPage: true })
  await page.getByRole('tab', { name: '评价规则' }).click()
  await expect(page.getByText('同级占 100%', { exact: true })).toBeVisible()
  await expect(page.getByRole('spinbutton')).toHaveCount(0)
  await page.getByRole('tab', { name: '人员安排' }).click()
  await expect(page.locator('.frozen-group')).toContainText(['发布时李四', '张三'])
  await page.getByRole('textbox', { name: '人员搜索' }).fill('发布时李四')
  await page.getByRole('textbox', { name: '人员搜索' }).press('Enter')
  await expect(page.getByText('发布时李四', { exact: true })).toBeVisible()
  await page.getByRole('textbox', { name: '人员搜索' }).fill('没有这个人')
  await page.getByRole('textbox', { name: '人员搜索' }).press('Enter')
  await expect(page.getByText('没有匹配的人员安排')).toBeVisible()
  await page.reload()
  await expect(page.getByRole('heading', { name: '发布详情', exact: true })).toBeVisible()
  expect(candidateCount()).toBe(0)
  expect(writes).toBe(0)
  await page.setViewportSize({ width: 900, height: 986 })
  await page.getByRole('tab', { name: '问卷与指标' }).click()
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBe(0)
})

test('评价安排展示分组姓名，切换和增删只影响当前员工的关系', async ({ page }) => {
  await page.setViewportSize({ width: 1534, height: 986 })
  const secondTarget = { userId: 20, nickName: '赵六', userName: 'zhaoliu', available: true }
  const peer = { userId: 12, nickName: '王五', userName: 'wangwu', deptName: '研发部', available: true }
  const anotherPeer = { userId: 13, nickName: '钱七', userName: 'qianqi', deptName: '人力部', available: true }
  const config = readyConfig()
  config.targets.push(secondTarget)
  config.relations[0] = { ...config.relations[0], isEnabled: true, participatesInScore: true, weight: '60.0000' }
  config.relations[1].weight = '40.0000'
  config.configuredParticipants = [...config.configuredParticipants, secondTarget, peer, anotherPeer]
  config.evaluatorSelections = [
    { targetUserId: 10, relationCode: 'REL_SUPERVISOR', evaluatorUserIds: [11] },
    { targetUserId: 10, relationCode: 'REL_PEER', evaluatorUserIds: [12, 13] },
    { targetUserId: 20, relationCode: 'REL_SUPERVISOR', evaluatorUserIds: [13] }
  ]
  await openPublicationWithPermissions(page, userInfo.permissions, config)
  let writes = 0
  page.on('request', request => { if (request.url().includes('/feedback/') && request.method() !== 'GET') writes += 1 })
  await page.getByRole('button', { name: '第5步：谁来评价', exact: true }).click()
  const panel = page.locator('.evaluator-panel')
  const group = name => panel.locator('.assignment-group').filter({ has: page.getByRole('button', { name, exact: true }) })
  const upperGroup = group('配置张三的上级评价人')
  const peerGroup = group('配置张三的同级评价人')
  await expect(upperGroup).toContainText('李四')
  await expect(peerGroup).toContainText('王五')
  await expect(peerGroup).toContainText('钱七')
  await expect(group('配置赵六的同级评价人')).toContainText('未分配')
  await peerGroup.getByRole('button').click()
  await expect(panel.getByText('已选同级评价人（2）', { exact: true })).toBeVisible()
  await expect(panel.getByRole('radio', { name: '同级2 人', exact: true })).toBeChecked()
  await expect(peerGroup.getByRole('button')).toHaveAttribute('aria-pressed', 'true')
  await panel.screenshot({ path: 'output/playwright/publication-evaluator-groups.png' })
  const candidate = panel.locator('.dual-list .list-column').first().getByRole('row').filter({ has: page.getByText('李四', { exact: true }) })
  await candidate.getByRole('button', { name: '添加', exact: true }).click()
  await expect(peerGroup).toContainText('3 人')
  await expect(peerGroup).toContainText('李四')
  await expect(upperGroup).toContainText('1 人')
  await expect(panel.getByText('已选同级评价人（3）', { exact: true })).toBeVisible()
  await group('配置赵六的上级评价人').getByRole('button').click()
  await expect(panel.locator('.assignment-context')).toContainText('赵六')
  await expect(panel.getByText('已选上级评价人（1）', { exact: true })).toBeVisible()
  await panel.locator('.selected-column').getByRole('button', { name: '移除', exact: true }).click()
  await expect(group('配置赵六的上级评价人')).toContainText('未分配')
  await expect(peerGroup).toContainText('3 人')
  await panel.locator('.relation-picker .el-radio-button').filter({ hasText: '同级' }).click()
  await expect(panel.getByText('已选同级评价人（0）', { exact: true })).toBeVisible()
  await expect(panel.locator('.selected-column')).toContainText('从左侧为赵六添加同级评价人')
  await expect.poll(() => panel.evaluate(el => el.closest('.el-card__body').scrollWidth - el.closest('.el-card__body').clientWidth)).toBe(0)
  expect(writes).toBe(0)
})

test('保存关系配置前后保持卡片宽度，窄屏仅表格内部滚动', async ({ page }) => {
  await page.setViewportSize({ width: 2050, height: 986 })
  const config = readyConfig()
  config.relations[0] = { ...config.relations[0], isEnabled: true, participatesInScore: true, weight: '60.0000' }
  config.relations[1].weight = '40.0000'
  await openPublicationWithPermissions(page, userInfo.permissions, config)
  let releaseSave
  let savedPayload
  await page.route('**/dev-api/feedback/projects/101/publication-config', async route => {
    if (route.request().method() !== 'PUT') return route.fulfill({ json: { code: 200, data: config } })
    savedPayload = route.request().postDataJSON()
    await new Promise(resolve => { releaseSave = resolve })
    await route.fulfill({ json: { code: 200, data: { ...config, relations: savedPayload.relations.map(row => ({ ...row, fixed: true })) } } })
  })
  await page.getByRole('button', { name: '第4步：设置评价关系', exact: true }).click()
  const panel = page.locator('.relation-panel')
  const overflow = () => panel.evaluate(el => {
    const card = el.closest('.el-card__body')
    const table = el.querySelector('.el-table')
    return {
      card: card.scrollWidth - card.clientWidth,
      panel: el.scrollWidth - el.clientWidth,
      table: table.getBoundingClientRect().width - el.getBoundingClientRect().width,
      document: document.documentElement.scrollWidth - document.documentElement.clientWidth
    }
  })
  await expect.poll(overflow).toEqual({ card: 0, panel: 0, table: 0, document: 0 })
  const beforeWidth = (await panel.boundingBox()).width
  await page.getByRole('button', { name: '保存配置', exact: true }).click()
  await expect(panel.getByRole('columnheader', { name: '操作', exact: true })).toHaveCount(0)
  await expect.poll(() => Boolean(releaseSave)).toBe(true)
  await expect.poll(overflow).toEqual({ card: 0, panel: 0, table: 0, document: 0 })
  releaseSave()
  await expect(page.getByText('配置已保存，发布前检查已通过')).toBeVisible()
  await expect(panel.getByRole('columnheader', { name: '操作', exact: true })).toBeVisible()
  await expect.poll(overflow).toEqual({ card: 0, panel: 0, table: 0, document: 0 })
  expect((await panel.boundingBox()).width).toBe(beforeWidth)
  await expect(panel.getByRole('spinbutton', { name: '上级权重（%）', exact: true })).toHaveValue('60')
  await expect(panel.getByRole('spinbutton', { name: '同级权重（%）', exact: true })).toHaveValue('40')
  expect(savedPayload.targets).toEqual([{ targetUserId: 10 }])
  await panel.screenshot({ path: 'output/playwright/publication-relations-after-save.png' })
  for (const width of [1466, 900, 2050]) {
    await page.setViewportSize({ width, height: 986 })
    await expect.poll(overflow).toEqual({ card: 0, panel: 0, table: 0, document: 0 })
  }
})

test('计分说明可展开，实时提示占比变化，保留未保存配置', async ({ page }) => {
  await page.setViewportSize({ width: 1682, height: 986 })
  const config = readyConfig()
  config.relations[0] = { ...config.relations[0], isEnabled: true, participatesInScore: true, weight: '60.0000' }
  config.relations[1].weight = '40.0000'
  await openPublicationWithPermissions(page, userInfo.permissions, config)
  let writes = 0
  page.on('request', request => {
    if (request.url().includes('/feedback/') && request.method() !== 'GET') writes += 1
  })
  await page.getByRole('button', { name: '第4步：设置评价关系', exact: true }).click()
  const panel = page.locator('.relation-panel')
  const summary = panel.getByRole('region', { name: '当前计分方式' })
  await expect(summary).toContainText('上级占 60%，同级占 40%')
  await expect(summary).toContainText('权重合计 100%')
  await expect(panel.getByRole('spinbutton', { name: '自己权重（%）' })).toHaveCount(0)
  await expect(panel.getByText('单独展示', { exact: true })).toBeVisible()
  await panel.getByRole('button', { name: '了解计入总分', exact: true }).click()
  await expect(page.getByRole('tooltip')).toContainText('不勾选时，评价结果仅供参考')
  await panel.getByRole('button', { name: '了解计入总分', exact: true }).click()
  await expect(panel.getByText('从题目到最终成绩', { exact: true })).not.toBeVisible()
  const summaryHeight = (await summary.boundingBox()).height
  expect(summaryHeight).toBeLessThan(64)
  const help = panel.getByRole('button', { name: '分数怎么算？', exact: true })
  await help.focus()
  await help.press('Enter')
  const guide = page.getByRole('region', { name: '计分规则说明' })
  await expect(guide.getByText('演示数据', { exact: true })).toBeVisible()
  await expect(guide.getByText('85.4 分', { exact: true })).toBeVisible()
  await guide.getByRole('button', { name: '有人未提交或漏答，会怎样？', exact: true }).click()
  await expect(guide.getByText(/报告会标明缺失情况/)).toBeVisible()
  await expect(guide.getByText(/不会用自评补上/)).toBeVisible()
  expect((await summary.boundingBox()).height).toBe(summaryHeight)
  await guide.screenshot({ path: 'output/playwright/publication-scoring-help.png' })
  await help.click()
  await expect(guide).not.toBeVisible()
  await help.click()
  await expect(guide).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(guide).not.toBeVisible()

  const upperInput = panel.getByRole('spinbutton', { name: '上级权重（%）', exact: true })
  await upperInput.fill('80')
  await upperInput.press('Tab')
  await expect(summary.getByRole('alert')).toContainText('已超出 20%，请减少占比')
  await expect(page.getByText('有未保存修改', { exact: true })).toBeVisible()
  await upperInput.fill('60')
  await upperInput.press('Tab')
  const peerRow = panel.locator('tr').filter({ has: page.getByRole('switch', { name: '启用同级', exact: true }) })
  await peerRow.locator('.el-checkbox').click()
  await expect(summary).toContainText('仅供参考：同级，不计入总分')
  await expect(summary.getByRole('alert')).toContainText('还差 40%，请补足占比')
  await peerRow.locator('.el-checkbox').click()
  const peerInput = peerRow.getByRole('spinbutton')
  await peerInput.fill('40')
  await peerInput.press('Tab')
  await expect(summary.getByRole('alert')).toContainText('占比已达标')
  await page.getByRole('button', { name: '上一步', exact: true }).click()
  await expect(page.locator('.selector-panel').getByText('已选 1 人')).toBeVisible()
  await page.getByRole('button', { name: '下一步：设置评价关系' }).click()
  await expect(upperInput).toHaveValue('60')
  await expect(peerInput).toHaveValue('40')
  expect(writes).toBe(0)
  await summary.screenshot({ path: 'output/playwright/publication-scoring-summary.png' })
})

test('HR配置目标和评价人、保存恢复、二次确认发布并进入只读', async ({ page }) => {
  await page.setViewportSize({ width: 1466, height: 986 })
  let persistedConfig = initialConfig()
  let published = false
  let savePayload
  let publishCount = 0

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
    route.fulfill({ json: { code: 200, token: 'p5-e2e-token' } })
  )
  await page.route('**/dev-api/getInfo', route => route.fulfill({ json: userInfo }))

  const handleFeedbackApi = async route => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname.replace('/dev-api', '')
    if (path === '/feedback/projects' && request.method() === 'GET') {
      return route.fulfill({
        json: {
          code: 200,
          rows: [
            {
              projectId: 101,
              projectName: 'P5浏览器验收项目',
              status: published ? 'ACTIVE' : 'PREPARING',
              lockVersion: persistedConfig.projectLockVersion,
              createBy: 'feedback-hr'
            }
          ],
          pageNum: 1,
          pageSize: 10,
          total: 1,
          hasNext: false
        }
      })
    }
    if (path === '/feedback/projects/101/participant-options' && request.method() === 'GET') {
      return route.fulfill({
        json: { code: 200, rows: candidates, pageNum: 1, pageSize: 10, total: 2, hasNext: false }
      })
    }
    if (path === '/feedback/projects/101/publication-config' && request.method() === 'GET') {
      return route.fulfill({ json: { code: 200, data: persistedConfig } })
    }
    if (path === '/feedback/projects/101/publication-config' && request.method() === 'PUT') {
      savePayload = request.postDataJSON()
      persistedConfig = {
        ...persistedConfig,
        projectLockVersion: savePayload.projectLockVersion + 1,
        versionLockVersion: savePayload.versionLockVersion + 1,
        targets: [
          { ...candidates[0], targetId: 301, onlySelfEvaluation: false }
        ],
        relations: savePayload.relations.map((item, index) => ({
          ...item,
          relationId: index + 1,
          fixed: true
        })),
        evaluatorSelections: [
          ...savePayload.evaluatorSelections.map(item => ({ ...item, systemManaged: false })),
          {
            targetUserId: candidates[0].userId,
            relationCode: 'REL_SELF',
            evaluatorUserIds: [candidates[0].userId],
            systemManaged: true
          }
        ],
        configuredParticipants: candidates,
        preview: {
          targetCount: 1,
          evaluatorCount: 2,
          assignmentCount: 2,
          targetSummaries: [
            { targetUserId: candidates[0].userId, selfCount: 1, nonSelfCount: 1, assignmentCount: 2 }
          ]
        },
        validationIssues: [],
        isPublishReady: true
      }
      return route.fulfill({ json: { code: 200, msg: '发布配置已保存', data: persistedConfig } })
    }
    if (path === '/feedback/projects/101/publish' && request.method() === 'POST') {
      publishCount += 1
      published = true
      persistedConfig = {
        ...persistedConfig,
        projectStatus: 'ACTIVE',
        projectLockVersion: persistedConfig.projectLockVersion + 1,
        versionStatus: 'FROZEN',
        versionLockVersion: persistedConfig.versionLockVersion + 1,
        editable: false,
        frozenDetails: frozenDetailsFixture()
      }
      return route.fulfill({
        json: {
          code: 200,
          msg: '项目发布成功',
          data: {
            projectId: 101,
            projectStatus: 'ACTIVE',
            versionId: 201,
            versionStatus: 'FROZEN',
            targetCount: 1,
            evaluatorCount: 2,
            assignmentCount: 2,
            alreadyPublished: false
          }
        }
      })
    }
    return route.fulfill({ status: 404, json: { code: 404, msg: '未匹配测试接口' } })
  }
  await page.route('**/dev-api/feedback/projects*', handleFeedbackApi)
  await page.route('**/dev-api/feedback/projects/**', handleFeedbackApi)

  await page.goto('/login')
  await page.getByLabel('账号').fill('feedback-hr')
  await page.getByLabel('密码').fill('secret')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await page.getByRole('button', { name: '配置并发布' }).click()

  await expect(page).toHaveURL(/\/hr\/projects\/101\/publication$/)
  await expect(page.getByRole('heading', { name: '人员关系与发布' })).toBeVisible()
  await expect(page.getByRole('button', { name: '发布项目', exact: true })).toHaveCount(0)
  await page.screenshot({ path: 'output/playwright/publication-wizard-targets.png', fullPage: true })
  const targetCard = page.locator('.selector-panel')
  await targetCard.getByRole('button', { name: '添加' }).first().click()
  await expect(targetCard.getByText('已选 1 人')).toBeVisible()
  await page.getByRole('button', { name: '下一步：设置评价关系' }).click()

  const relationCard = page.locator('.relation-panel')
  const peerRow = relationCard.locator('tr').filter({ has: page.getByRole('switch', { name: '启用同级', exact: true }) })
  await expect(peerRow.getByRole('spinbutton')).toHaveValue('0')
  await peerRow.locator('.el-switch').click()
  await peerRow.locator('.el-checkbox').click()
  const weightInput = peerRow.getByRole('spinbutton')
  await expect(weightInput).toHaveValue('100')
  await weightInput.fill('60.6')
  await weightInput.press('Tab')
  await expect(weightInput).toHaveValue('61')
  await weightInput.press('ArrowUp')
  await expect(weightInput).toHaveValue('62')
  await weightInput.fill('120')
  await weightInput.press('Tab')
  await expect(weightInput).toHaveValue('100')
  await weightInput.fill('-1')
  await weightInput.press('Tab')
  await expect(weightInput).toHaveValue('0')
  await weightInput.fill('100')
  await weightInput.press('Tab')
  await page.screenshot({ path: 'output/playwright/publication-wizard-relations.png', fullPage: true })
  await page.getByRole('button', { name: '下一步：谁来评价' }).click()
  await expect(page.locator('.assignment-issues').getByText('“同级”尚未分配评价人')).toBeVisible()

  const evaluatorCard = page.locator('.evaluator-panel')
  const evaluatorRow = evaluatorCard.locator('tr').filter({ hasText: '李四' }).first()
  await evaluatorRow.getByRole('button', { name: '添加' }).click()
  await expect(evaluatorCard.getByText('已选同级评价人（1）')).toBeVisible()
  await page.getByRole('button', { name: '上一步', exact: true }).click()
  await page.getByRole('button', { name: '下一步：谁来评价' }).click()
  await expect(evaluatorCard.getByText('已选同级评价人（1）')).toBeVisible()
  await page.screenshot({ path: 'output/playwright/publication-wizard-evaluators.png', fullPage: true })

  await page.getByRole('button', { name: '保存并检查发布条件' }).click()
  await expect(page.getByText('配置已保存，发布前检查已通过')).toBeVisible()
  expect(savePayload.evaluatorSelections).toEqual([
    { targetUserId: 10, relationCode: 'REL_PEER', evaluatorUserIds: [11] }
  ])
  expect(savePayload.evaluatorSelections.some(item => item.relationCode === 'REL_SELF')).toBe(false)
  expect(savePayload.relations.find(item => item.relationCode === 'REL_PEER').weight).toBe('100.0000')

  const previewCard = page.locator('.preview-panel')
  await expect(previewCard.getByText('可以发布')).toBeVisible()
  await expect(previewCard.getByText('任务总数')).toBeVisible()
  await expect(previewCard.getByText('张三', { exact: true })).toBeVisible()
  await page.screenshot({ path: 'output/playwright/publication-wizard-review.png', fullPage: true })
  await page.reload()
  await expect(previewCard.getByText('可以发布')).toBeVisible()
  await page.getByRole('button', { name: '第4步：设置评价关系', exact: true }).click()
  await expect(page.getByRole('spinbutton', { name: '同级权重（%）', exact: true })).toHaveValue('100')
  await page.getByRole('button', { name: '第6步：检查并发布', exact: true }).click()

  await page.getByRole('button', { name: '发布项目' }).click()
  const confirmDialog = page.getByRole('dialog', { name: '确认发布项目' })
  await expect(confirmDialog.getByText(/生成2项任务/)).toBeVisible()
  await confirmDialog.getByRole('button', { name: '确认发布' }).click()
  await expect(page.getByText('项目发布成功')).toBeVisible()
  await expect(page.getByText('已冻结只读')).toBeVisible()
  await expect(page.getByRole('button', { name: '保存配置' })).toHaveCount(0)
  expect(publishCount).toBe(1)

  await page.reload()
  await expect(page.getByRole('heading', { name: '发布详情', exact: true })).toBeVisible()
  await expect(page.getByText('已发布 · 以下配置已锁定，供查阅和核对。')).toBeVisible()
  await expect(page.getByText('已冻结只读')).toBeVisible()
})

test('仅自评跳过分配，保存失败可重试，返回修改后重新检查', async ({ page }) => {
  let persisted = initialConfig()
  await openPublicationWithPermissions(page, userInfo.permissions, persisted)
  let fail = true
  let payload
  await page.route('**/dev-api/feedback/projects/101/publication-config', route => {
    if (route.request().method() !== 'PUT') return route.fulfill({ json: { code: 200, data: persisted } })
    if (fail) {
      fail = false
      return route.fulfill({ status: 500, json: { code: 500, msg: '测试保存失败，请重试' } })
    }
    payload = route.request().postDataJSON()
    persisted = { ...persisted, targets: [candidates[0]], isPublishReady: true, validationIssues: [],
      preview: { targetCount: 1, evaluatorCount: 1, assignmentCount: 1, targetSummaries: [{ targetUserId: 10, selfCount: 1, nonSelfCount: 0, assignmentCount: 1 }] } }
    return route.fulfill({ json: { code: 200, data: persisted } })
  })
  await page.locator('.selector-panel').getByRole('button', { name: '添加', exact: true }).first().click()
  await page.getByRole('button', { name: '下一步：设置评价关系' }).click()
  await page.locator('.evaluation-mode .el-radio-button').filter({ hasText: '仅自评' }).click()
  await page.getByRole('button', { name: '保存并检查发布条件' }).click()
  await expect(page.getByText('测试保存失败，请重试')).toBeVisible()
  await expect(page.getByRole('radio', { name: '仅自评', exact: true })).toBeChecked()
  // 等待读完错误提示后重试，遵守共享请求层的 1500ms 防重复提交间隔。
  await expect(page.getByText('测试保存失败，请重试')).toBeHidden()
  await page.getByRole('button', { name: '保存并检查发布条件' }).click()
  await expect(page.locator('.preview-panel').getByText('可以发布')).toBeVisible()
  expect(payload.evaluatorSelections).toEqual([])
  expect(payload.targets).toEqual([{ targetUserId: 10 }])
  await page.getByRole('button', { name: '上一步', exact: true }).click()
  await expect(page.getByRole('radio', { name: '仅自评', exact: true })).toBeVisible()
  await page.getByRole('button', { name: '上一步', exact: true }).click()
  await expect(page.locator('.selector-panel').getByText('已选 1 人')).toBeVisible()
})

test('仅人员管理权限可进入配置页且只能保存', async ({ page }) => {
  const candidateCount = await openPublicationWithPermissions(
    page,
    ['feedback:project:list', 'feedback:participant:manage'],
    initialConfig()
  )

  await expect(page.getByRole('button', { name: '保存配置' })).toBeVisible()
  await expect(page.getByRole('button', { name: '发布项目' })).toHaveCount(0)
  expect(candidateCount()).toBe(1)
})

test('两处人员搜索回车仅查询一次，不刷新页面且保留未保存配置', async ({ page }) => {
  await openPublicationWithPermissions(page, userInfo.permissions, initialConfig())
  const navigations = []
  const queries = []
  page.on('request', request => {
    if (request.isNavigationRequest() && request.frame() === page.mainFrame()) navigations.push(request.url())
  })
  await page.route('**/dev-api/feedback/projects/101/participant-options*', route => {
    const keyword = new URL(route.request().url()).searchParams.get('keyword') || ''
    queries.push(keyword)
    const rows = candidates.filter(item => `${item.nickName} ${item.userName}`.includes(keyword))
    return route.fulfill({ json: { code: 200, rows, total: rows.length } })
  })
  const targets = page.locator('.selector-panel')
  await targets.getByRole('button', { name: '添加', exact: true }).first().click()
  await targets.getByRole('textbox', { name: '人员搜索' }).fill(' 李四 ')
  const targetResponse = page.waitForResponse(response => response.url().includes('participant-options') && new URL(response.url()).searchParams.get('keyword') === '李四')
  await targets.getByRole('textbox', { name: '人员搜索' }).press('Enter')
  await targetResponse
  await expect(targets.getByText('已选 1 人')).toBeVisible()
  await expect(targets.locator('.selected-column').getByText('张三', { exact: true })).toBeVisible()
  await expect(targets.locator('.list-column').first().getByText('张三', { exact: true })).toHaveCount(0)
  expect(queries).toEqual(['李四'])
  expect(navigations).toEqual([])

  await page.getByRole('button', { name: '下一步：设置评价关系' }).click()
  const peerRow = page.locator('.relation-panel tr').filter({ has: page.getByRole('switch', { name: '启用同级', exact: true }) })
  await peerRow.locator('.el-switch').click()
  await peerRow.locator('.el-checkbox').click()
  await page.getByRole('button', { name: '下一步：谁来评价' }).click()
  const evaluators = page.locator('.evaluator-panel')
  await evaluators.getByRole('button', { name: '添加', exact: true }).click()
  await evaluators.getByRole('textbox', { name: '人员搜索' }).fill('张三')
  const evaluatorResponse = page.waitForResponse(response => response.url().includes('participant-options') && new URL(response.url()).searchParams.get('keyword') === '张三')
  await evaluators.getByRole('textbox', { name: '人员搜索' }).press('Enter')
  await evaluatorResponse
  await expect(evaluators.getByText('已选同级评价人（1）')).toBeVisible()
  await expect(evaluators.locator('.selected-column').getByText('李四', { exact: true })).toBeVisible()
  await expect(page.getByText('有未保存修改')).toBeVisible()
  expect(queries).toEqual(['李四', '张三'])
  expect(navigations).toEqual([])
})

test('仅发布权限可进入配置页且不能修改人员配置', async ({ page }) => {
  const candidateCount = await openPublicationWithPermissions(
    page,
    ['feedback:project:list', 'feedback:project:publish'],
    readyConfig()
  )

  await expect(page.getByRole('button', { name: '保存配置' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '发布项目' })).toBeEnabled()
  await expect(page.getByRole('button', { name: '移除' })).toHaveCount(0)
  expect(candidateCount()).toBe(0)
})
