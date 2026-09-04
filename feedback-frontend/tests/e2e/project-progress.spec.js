import { expect, test } from '@playwright/test'

const permissions = ['feedback:project:list', 'feedback:progress:view', 'feedback:project:complete']

function summary(overrides = {}) {
  return {
    totalCount: 3,
    submittedCount: 1,
    draftCount: 1,
    pendingCount: 1,
    closedIncompleteCount: 0,
    incompleteCount: 2,
    completionRate: '33.33',
    ...overrides
  }
}

function progress(overrides = {}) {
  return {
    projectId: 12,
    projectName: 'P7回收项目',
    projectStatus: 'ACTIVE',
    projectLockVersion: 3,
    dataScopeComplete: true,
    scopeMessage: null,
    summary: summary(),
    filterOptions: { relations: [{ relationId: 8, relationCode: 'PEER', relationName: '同级', sortOrder: 1 }] },
    rows: [
      { assignmentId: 1, evaluatorUserId: 10, evaluatorName: '张三', evaluatorDeptName: '研发部', targetUserId: 20, targetName: '李四', targetDeptName: '产品部', relationId: 8, relationCode: 'PEER', relationName: '同级', status: 'SUBMITTED', submittedTime: '2026-09-02T10:00:00' },
      { assignmentId: 2, evaluatorUserId: 11, evaluatorName: '王五', evaluatorDeptName: '研发部', targetUserId: 20, targetName: '李四', targetDeptName: '产品部', relationId: 8, relationCode: 'PEER', relationName: '同级', status: 'DRAFT', savedTime: '2026-09-02T10:01:00' },
      { assignmentId: 3, evaluatorUserId: 12, evaluatorName: '赵六', evaluatorDeptName: '研发部', targetUserId: 20, targetName: '李四', targetDeptName: '产品部', relationId: 8, relationCode: 'PEER', relationName: '同级', status: 'PENDING' }
    ],
    total: 3,
    pageNum: 1,
    pageSize: 20,
    ...overrides
  }
}

function completionPrecheck(overrides = {}) {
  return {
    projectId: 12,
    projectName: 'P7回收项目',
    projectStatus: 'ACTIVE',
    projectLockVersion: 3,
    dataScopeComplete: true,
    canComplete: true,
    completedBy: null,
    completedTime: null,
    completionReason: null,
    alreadyCompleted: false,
    summary: summary(),
    missingRelations: [],
    impactMessages: [],
    precheckedAt: '2026-09-02T10:05:00',
    ...overrides
  }
}

async function mockBase(page, userPermissions = permissions) {
  await page.route('**/dev-api/transport/crypto/frontend-config', route => route.fulfill({ json: { code: 200, data: { transportCryptoEnabled: false, transportCryptoMode: 'off', transportCryptoActive: false, configExpireAt: Math.floor(Date.now() / 1000) + 300 } } }))
  await page.route('**/dev-api/captchaImage', route => route.fulfill({ json: { code: 200, captchaEnabled: false } }))
  await page.route('**/dev-api/login', route => route.fulfill({ json: { code: 200, token: 'p7-token' } }))
  await page.route('**/dev-api/getInfo', route => route.fulfill({ json: { code: 200, user: { userId: 2, userName: 'hr', nickName: '评价HR' }, roles: ['feedback_hr'], permissions: userPermissions } }))
}

async function login(page) {
  await page.goto('/login')
  await page.getByLabel('账号').fill('hr')
  await page.getByLabel('密码').fill('secret')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL(/\/hr\/projects$/)
}

test('有未提交任务时禁用完成，HR通过提前结束预检确认并刷新为只读状态', async ({ page }) => {
  await mockBase(page)
  let completed = false
  let completeCount = 0
  let completePayload
  const handle = async route => {
    const request = route.request()
    const path = new URL(request.url()).pathname.replace('/dev-api', '')
    if (path === '/feedback/projects' && request.method() === 'GET') return route.fulfill({ json: { code: 200, rows: [{ projectId: 12, projectName: 'P7回收项目', status: completed ? 'COMPLETED' : 'ACTIVE', lockVersion: completed ? 4 : 3 }], total: 1, pageNum: 1, pageSize: 10 } })
    if (path === '/feedback/projects/12/progress') return route.fulfill({ json: { code: 200, data: completed ? progress({ projectStatus: 'COMPLETED', projectLockVersion: 4, summary: summary({ draftCount: 0, pendingCount: 0, closedIncompleteCount: 2 }), rows: progress().rows.map(row => row.status === 'SUBMITTED' ? row : { ...row, status: 'CLOSED_INCOMPLETE', closedTime: '2026-09-02T10:06:00' }) }) : progress() } })
    if (path === '/feedback/projects/12/completion-precheck') return route.fulfill({ json: { code: 200, data: completionPrecheck({ missingRelations: [{ targetUserId: 20, targetName: '李四', relationId: 8, relationName: '同级', assignmentCount: 3, submittedCount: 1 }], impactMessages: ['完成后1项已暂存任务和1项未开始任务将关闭且不可继续作答。', '报告只会使用1项已提交答卷；缺失关系不会按0分处理。'] }) } })
    if (path === '/feedback/projects/12/complete' && request.method() === 'POST') {
      completeCount += 1
      completePayload = request.postDataJSON()
      completed = true
      return route.fulfill({ json: { code: 200, msg: '项目已完成', data: { projectId: 12, projectStatus: 'COMPLETED', projectLockVersion: 4, completedBy: 2, completedTime: '2026-09-02T10:06:00', completionReason: completePayload.completionReason, alreadyCompleted: false, summary: summary({ draftCount: 0, pendingCount: 0, closedIncompleteCount: 2 }) } } })
    }
    if (path === '/feedback/projects/12') return route.fulfill({ json: { code: 200, data: { projectId: 12, status: completed ? 'COMPLETED' : 'ACTIVE', completionReason: completed ? '本轮评价截止' : null } } })
    return route.fulfill({ status: 404, json: { code: 404, msg: '未匹配P7测试接口' } })
  }
  await page.route('**/dev-api/feedback/projects*', handle)
  await page.route('**/dev-api/feedback/projects/**', handle)
  await login(page)

  await page.getByRole('button', { name: '评价进度' }).click()
  await expect(page).toHaveURL(/\/hr\/projects\/12\/progress$/)
  await expect(page.getByRole('heading', { name: '评价进度', exact: true })).toBeVisible()
  await expect(page.getByText('33.33%')).toBeVisible()
  await expect(page.getByText('张三').first()).toBeVisible()
  await expect(page.getByRole('button', { name: '完成项目', exact: true })).toBeDisabled()
  await expect(page.getByText('还有 2 份未提交', { exact: true })).toBeVisible()
  expect(completeCount).toBe(0)

  await page.getByRole('button', { name: '提前结束', exact: true }).click()
  const drawer = page.getByRole('dialog', { name: '提前结束项目确认' })
  await expect(drawer.getByText('还有 2 份评价未提交', { exact: true })).toBeVisible()
  await expect(drawer.getByText('确认后，剩余 2 份任务将关闭，员工不能继续填写；报告仅使用 1 份已提交答卷。项目结束后不能重新打开。')).toBeVisible()
  await expect(drawer.getByRole('button', { name: '确认提前结束', exact: true })).toBeDisabled()
  await expect(drawer.getByText('完成后1项已暂存任务和1项未开始任务将关闭且不可继续作答。')).toBeVisible()
  await drawer.getByLabel('完成原因').fill('  本轮评价截止  ')
  await drawer.locator('.el-checkbox').click()
  await drawer.getByRole('button', { name: '确认提前结束', exact: true }).click()

  await expect(page.getByText('已完成').first()).toBeVisible()
  await expect(page.getByRole('button', { name: '完成项目' })).toHaveCount(0)
  expect(completeCount).toBe(1)
  expect(completePayload).toEqual({ projectLockVersion: 3, completionReason: '本轮评价截止', expectedSummary: { totalCount: 3, submittedCount: 1, draftCount: 1, pendingCount: 1, closedIncompleteCount: 0 } })
  await expect(page.getByText('查看答案')).toHaveCount(0)
  await expect(page.getByText('导出')).toHaveCount(0)
})

test('全部提交后仅提供正常完成入口，点击先预检且不直接发送完成请求', async ({ page }) => {
  await mockBase(page)
  const full = summary({ submittedCount: 3, draftCount: 0, pendingCount: 0, incompleteCount: 0, completionRate: '100.00' })
  let precheckCount = 0
  let completeCount = 0
  const handle = route => {
    const path = new URL(route.request().url()).pathname.replace('/dev-api', '')
    if (path === '/feedback/projects') return route.fulfill({ json: { code: 200, rows: [{ projectId: 12, projectName: 'P7回收项目', status: 'ACTIVE', lockVersion: 3 }], total: 1 } })
    if (path === '/feedback/projects/12/progress') return route.fulfill({ json: { code: 200, data: progress({ summary: full, rows: progress().rows.map(row => ({ ...row, status: 'SUBMITTED' })) }) } })
    if (path === '/feedback/projects/12/completion-precheck') {
      precheckCount += 1
      return route.fulfill({ json: { code: 200, data: completionPrecheck({ summary: full }) } })
    }
    if (path === '/feedback/projects/12/complete') completeCount += 1
    return route.fulfill({ status: 404, json: { code: 404, msg: '未匹配P7测试接口' } })
  }
  await page.route('**/dev-api/feedback/projects*', handle)
  await page.route('**/dev-api/feedback/projects/**', handle)
  await login(page)
  await page.getByRole('button', { name: '评价进度', exact: true }).click()
  await expect(page.getByText('全部评价已提交', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '提前结束', exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '完成项目', exact: true })).toBeEnabled()
  await page.getByRole('button', { name: '完成项目', exact: true }).click()
  const drawer = page.getByRole('dialog', { name: '完成项目实时预检' })
  await expect(drawer).toBeVisible()
  await expect(drawer.getByRole('button', { name: '确认完成项目', exact: true })).toBeDisabled()
  await expect(drawer.getByRole('button', { name: '确认提前结束', exact: true })).toHaveCount(0)
  await drawer.getByRole('button', { name: '关闭', exact: true }).click()
  expect(precheckCount).toBe(1)
  expect(completeCount).toBe(0)
})

test('409统计变化关闭旧确认且不会自动重发完成请求', async ({ page }) => {
  await mockBase(page)
  let completeCount = 0
  const latest = completionPrecheck({ projectLockVersion: 4, summary: summary({ submittedCount: 2, draftCount: 0 }) })
  const handle = route => {
    const request = route.request()
    const path = new URL(request.url()).pathname.replace('/dev-api', '')
    if (path === '/feedback/projects') return route.fulfill({ json: { code: 200, rows: [{ projectId: 12, projectName: 'P7回收项目', status: 'ACTIVE', lockVersion: 3 }], total: 1 } })
    if (path === '/feedback/projects/12/progress') return route.fulfill({ json: { code: 200, data: progress() } })
    if (path === '/feedback/projects/12/completion-precheck') return route.fulfill({ json: { code: 200, data: completionPrecheck({ impactMessages: ['请确认最新统计。'] }) } })
    if (path === '/feedback/projects/12/complete') { completeCount += 1; return route.fulfill({ status: 409, json: { code: 409, msg: '回收统计已变化', data: { code: 'COMPLETION_PRECHECK_STALE', latestPrecheck: latest } } }) }
    return route.fulfill({ status: 404, json: { code: 404, msg: '未匹配P7测试接口' } })
  }
  await page.route('**/dev-api/feedback/projects*', handle)
  await page.route('**/dev-api/feedback/projects/**', handle)
  await login(page)
  await page.getByRole('button', { name: '评价进度' }).click()
  await page.getByRole('button', { name: '提前结束', exact: true }).click()
  const drawer = page.getByRole('dialog', { name: '提前结束项目确认' })
  await drawer.getByLabel('完成原因').fill('本轮截止')
  await drawer.locator('.el-checkbox').click()
  await drawer.getByRole('button', { name: '确认提前结束', exact: true }).click()
  await expect(drawer).toHaveCount(0)
  await expect(page.getByText('回收数据已变化，请重新阅读最新预检并再次确认。')).toBeVisible()
  await expect(page.getByText('2').first()).toBeVisible()
  expect(completeCount).toBe(1)
})

test('390px完成抽屉正文和确认复选框不产生横向溢出', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await mockBase(page)
  const handle = route => {
    const request = route.request()
    const path = new URL(request.url()).pathname.replace('/dev-api', '')
    if (path === '/feedback/projects') return route.fulfill({ json: { code: 200, rows: [{ projectId: 12, projectName: 'P7回收项目', status: 'ACTIVE', lockVersion: 3 }], total: 1, pageNum: 1, pageSize: 10 } })
    if (path === '/feedback/projects/12/progress') return route.fulfill({ json: { code: 200, data: progress() } })
    if (path === '/feedback/projects/12/completion-precheck') return route.fulfill({ json: { code: 200, data: completionPrecheck({ impactMessages: ['完成后1项已暂存任务和1项未开始任务将关闭且不可继续作答。'] }) } })
    return route.fulfill({ status: 404, json: { code: 404, msg: '未匹配P7测试接口' } })
  }
  await page.route('**/dev-api/feedback/projects*', handle)
  await page.route('**/dev-api/feedback/projects/**', handle)
  await login(page)
  await page.getByRole('button', { name: '评价进度' }).click()
  await page.getByRole('button', { name: '提前结束', exact: true }).click()
  const drawer = page.getByRole('dialog', { name: '提前结束项目确认' })
  await expect(drawer).toBeVisible()

  const bodySize = await drawer.locator('.el-drawer__body').evaluate(element => ({
    clientWidth: element.clientWidth,
    scrollWidth: element.scrollWidth
  }))
  expect(bodySize.scrollWidth).toBeLessThanOrEqual(bodySize.clientWidth)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
})

test('progress-only用户从安全入口进入进度页且不会请求项目详情', async ({ page }) => {
  await mockBase(page, ['feedback:progress:view'])
  let detailRequestCount = 0
  await page.route('**/dev-api/feedback/projects/**', route => {
    const path = new URL(route.request().url()).pathname.replace('/dev-api', '')
    if (path === '/feedback/projects/12/progress') {
      return route.fulfill({ json: { code: 200, data: progress() } })
    }
    if (path === '/feedback/projects/12') detailRequestCount += 1
    return route.fulfill({ status: 404, json: { code: 404, msg: '未匹配P7测试接口' } })
  })
  await page.goto('/login')
  await page.getByLabel('账号').fill('hr')
  await page.getByLabel('密码').fill('secret')
  await page.getByRole('button', { name: '登录', exact: true }).click()

  await expect(page).toHaveURL(/\/hr\/progress$/)
  await expect(page.getByRole('heading', { name: '评价进度' })).toBeVisible()
  await expect(page.getByRole('menuitem', { name: '评价进度' })).toBeVisible()
  await expect(page.getByRole('menuitem', { name: '项目管理' })).toHaveCount(0)
  await page.getByRole('spinbutton', { name: '项目ID' }).fill('12')
  await page.getByRole('button', { name: '查看评价进度' }).click()
  await expect(page).toHaveURL(/\/hr\/projects\/12\/progress$/)
  await expect(page.getByRole('button', { name: '返回评价进度入口' })).toBeVisible()
  expect(detailRequestCount).toBe(0)
})

test('complete-only用户不能进入需要progress:view的进度页', async ({ page }) => {
  await mockBase(page, ['feedback:project:complete'])
  let progressRequestCount = 0
  await page.route('**/dev-api/feedback/projects/**', route => {
    progressRequestCount += 1
    return route.fulfill({ status: 403, json: { code: 403, msg: '无权访问' } })
  })
  await page.goto('/login?redirect=/hr/projects/12/progress')
  await page.getByLabel('账号').fill('hr')
  await page.getByLabel('密码').fill('secret')
  await page.getByRole('button', { name: '登录', exact: true }).click()

  await expect(page).toHaveURL(/\/403$/)
  expect(progressRequestCount).toBe(0)
})

test('预检发现并发已完成后刷新终态并打开只读审计抽屉', async ({ page }) => {
  await mockBase(page)
  let concurrentCompleted = false
  const completedSummary = summary({ draftCount: 0, pendingCount: 0, closedIncompleteCount: 2 })
  const handle = route => {
    const request = route.request()
    const path = new URL(request.url()).pathname.replace('/dev-api', '')
    if (path === '/feedback/projects') return route.fulfill({ json: { code: 200, rows: [{ projectId: 12, projectName: 'P7回收项目', status: 'ACTIVE', lockVersion: 3 }], total: 1 } })
    if (path === '/feedback/projects/12/completion-precheck') {
      concurrentCompleted = true
      return route.fulfill({ json: { code: 200, data: completionPrecheck({ projectStatus: 'COMPLETED', projectLockVersion: 4, canComplete: false, completedBy: 7, completedTime: '2026-09-02T10:06:00', completionReason: '其他HR已完成', alreadyCompleted: true, summary: completedSummary }) } })
    }
    if (path === '/feedback/projects/12/progress') return route.fulfill({ json: { code: 200, data: progress({ projectStatus: concurrentCompleted ? 'COMPLETED' : 'ACTIVE', projectLockVersion: concurrentCompleted ? 4 : 3, summary: concurrentCompleted ? completedSummary : summary() }) } })
    if (path === '/feedback/projects/12') return route.fulfill({ json: { code: 200, data: { projectId: 12, projectName: 'P7回收项目', status: concurrentCompleted ? 'COMPLETED' : 'ACTIVE', lockVersion: concurrentCompleted ? 4 : 3 } } })
    return route.fulfill({ status: 404, json: { code: 404, msg: '未匹配P7测试接口' } })
  }
  await page.route('**/dev-api/feedback/projects*', handle)
  await page.route('**/dev-api/feedback/projects/**', handle)
  await login(page)
  await page.getByRole('button', { name: '评价进度' }).click()
  await page.getByRole('button', { name: '提前结束', exact: true }).click()

  const drawer = page.getByRole('dialog', { name: '完成项目实时预检' })
  await expect(drawer.getByText('完成操作人ID：7')).toBeVisible()
  await expect(drawer.getByText('完成时间：2026-09-02 10:06:00')).toBeVisible()
  await expect(drawer.getByText('完成原因：其他HR已完成')).toBeVisible()
  await expect(drawer.getByRole('button', { name: '确认完成项目' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: '完成项目' })).toHaveCount(0)
})

test('完成范围被收窄时立即清空旧明细且刷新失败也不回显', async ({ page }) => {
  await mockBase(page)
  let progressRequestCount = 0
  const handle = route => {
    const request = route.request()
    const path = new URL(request.url()).pathname.replace('/dev-api', '')
    if (path === '/feedback/projects') return route.fulfill({ json: { code: 200, rows: [{ projectId: 12, projectName: 'P7回收项目', status: 'ACTIVE', lockVersion: 3 }], total: 1 } })
    if (path === '/feedback/projects/12/progress') {
      progressRequestCount += 1
      if (progressRequestCount === 1) return route.fulfill({ json: { code: 200, data: progress() } })
      return route.fulfill({ status: 403, json: { code: 403, msg: '进度范围已收窄', data: { code: 'FORBIDDEN' } } })
    }
    if (path === '/feedback/projects/12/completion-precheck') return route.fulfill({ json: { code: 200, data: completionPrecheck() } })
    if (path === '/feedback/projects/12/complete') return route.fulfill({ status: 403, json: { code: 403, msg: '当前数据范围不能覆盖全部被评价人', data: { code: 'PROJECT_COMPLETION_SCOPE_FORBIDDEN' } } })
    if (path === '/feedback/projects/12') return route.fulfill({ json: { code: 200, data: { projectId: 12, projectName: 'P7回收项目', status: 'ACTIVE', lockVersion: 3 } } })
    return route.fulfill({ status: 404, json: { code: 404, msg: '未匹配P7测试接口' } })
  }
  await page.route('**/dev-api/feedback/projects*', handle)
  await page.route('**/dev-api/feedback/projects/**', handle)
  await login(page)
  await page.getByRole('button', { name: '评价进度' }).click()
  await expect(page.getByText('张三').first()).toBeVisible()
  await page.getByRole('button', { name: '提前结束', exact: true }).click()
  const drawer = page.getByRole('dialog', { name: '提前结束项目确认' })
  await drawer.getByLabel('完成原因').fill('本轮截止')
  await drawer.locator('.el-checkbox').click()
  await drawer.getByRole('button', { name: '确认提前结束', exact: true }).click()

  await expect(page.getByText('当前数据范围不能覆盖全部被评价人，禁止完成整个项目。')).toBeVisible()
  await expect(page.getByText('张三')).toHaveCount(0)
  await expect(page.locator('.progress-table tbody tr')).toHaveCount(0)
  expect(progressRequestCount).toBe(2)
})

test('完成请求5xx后锁定且重新核对ACTIVE不自动重发', async ({ page }) => {
  await mockBase(page)
  let completeCount = 0
  let precheckCount = 0
  const handle = route => {
    const request = route.request()
    const path = new URL(request.url()).pathname.replace('/dev-api', '')
    if (path === '/feedback/projects') return route.fulfill({ json: { code: 200, rows: [{ projectId: 12, projectName: 'P7回收项目', status: 'ACTIVE', lockVersion: 3 }], total: 1 } })
    if (path === '/feedback/projects/12/progress') return route.fulfill({ json: { code: 200, data: progress() } })
    if (path === '/feedback/projects/12/completion-precheck') { precheckCount += 1; return route.fulfill({ json: { code: 200, data: completionPrecheck() } }) }
    if (path === '/feedback/projects/12/complete') { completeCount += 1; return route.fulfill({ status: 503, json: { code: 503, msg: '网关暂不可用' } }) }
    if (path === '/feedback/projects/12') return route.fulfill({ json: { code: 200, data: { projectId: 12, projectName: 'P7回收项目', status: 'ACTIVE', lockVersion: 3 } } })
    return route.fulfill({ status: 404, json: { code: 404, msg: '未匹配P7测试接口' } })
  }
  await page.route('**/dev-api/feedback/projects*', handle)
  await page.route('**/dev-api/feedback/projects/**', handle)
  await login(page)
  await page.getByRole('button', { name: '评价进度' }).click()
  await page.getByRole('button', { name: '提前结束', exact: true }).click()
  const drawer = page.getByRole('dialog', { name: '提前结束项目确认' })
  await drawer.getByLabel('完成原因').fill('本轮截止')
  await drawer.locator('.el-checkbox').click()
  await drawer.getByRole('button', { name: '确认提前结束', exact: true }).click()

  await expect(page.getByText('完成请求可能已经到达服务端，当前结果未知。请先重新核对，系统不会自动重发完成请求。')).toBeVisible()
  await expect(page.getByRole('button', { name: '完成项目' })).toBeDisabled()
  await expect(page.getByRole('button', { name: '提前结束', exact: true })).toBeDisabled()
  expect(completeCount).toBe(1)
  await page.getByRole('button', { name: '重新核对' }).click()
  await expect(page.getByText('服务端仍显示项目进行中；如需再次完成，请重新执行实时预检。')).toBeVisible()
  expect(completeCount).toBe(1)
  expect(precheckCount).toBe(1)
  await page.getByRole('button', { name: '提前结束', exact: true }).click()
  await expect(page.getByRole('dialog', { name: '提前结束项目确认' })).toBeVisible()
  expect(precheckCount).toBe(2)
  expect(completeCount).toBe(1)
})

test('普通员工被进度路由守卫拒绝', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await mockBase(page, ['feedback:task:view'])
  await page.route('**/dev-api/feedback/projects/**', route => route.fulfill({ status: 403, json: { code: 403, msg: '无权访问' } }))
  await page.goto('/login?redirect=/hr/projects/12/progress')
  await page.getByLabel('账号').fill('employee')
  await page.getByLabel('密码').fill('secret')
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL(/\/403$/)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true)
})
