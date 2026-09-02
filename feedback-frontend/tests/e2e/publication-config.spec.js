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
          rows: [{ projectId: 101, projectName: '权限测试项目', status: 'PREPARING', lockVersion: 1 }],
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
  await page.getByRole('button', { name: '配置并发布' }).click()
  await expect(page.getByRole('heading', { name: '人员关系与发布' })).toBeVisible()
  return () => candidateRequestCount
}

test('HR配置目标和评价人、保存恢复、二次确认发布并进入只读', async ({ page }) => {
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
        editable: false
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
  const targetCard = page.locator('.selector-panel')
  await targetCard.getByRole('button', { name: '添加' }).first().click()
  await expect(targetCard.getByText('已选 1 人')).toBeVisible()

  const relationCard = page.locator('.relation-panel')
  const peerRow = relationCard.locator('tr').filter({ hasText: 'PEER' })
  await peerRow.locator('.el-switch').click()
  await peerRow.locator('.el-checkbox').click()

  const evaluatorCard = page.locator('.evaluator-panel')
  const evaluatorRow = evaluatorCard.locator('tr').filter({ hasText: '李四' }).first()
  await evaluatorRow.getByRole('button', { name: '添加' }).click()
  await expect(evaluatorCard.getByText('已选评价人（1）')).toBeVisible()

  await page.getByRole('button', { name: '保存配置' }).click()
  await expect(page.getByText('配置已保存，发布前检查已通过')).toBeVisible()
  expect(savePayload.evaluatorSelections).toEqual([
    { targetUserId: 10, relationCode: 'REL_PEER', evaluatorUserIds: [11] }
  ])
  expect(savePayload.evaluatorSelections.some(item => item.relationCode === 'REL_SELF')).toBe(false)

  const previewCard = page.locator('.preview-panel')
  await expect(previewCard.getByText('可以发布')).toBeVisible()
  await expect(previewCard.getByText('任务总数')).toBeVisible()

  await page.getByRole('button', { name: '发布项目' }).click()
  const confirmDialog = page.getByRole('dialog', { name: '确认发布项目' })
  await expect(confirmDialog.getByText(/生成2项任务/)).toBeVisible()
  await confirmDialog.getByRole('button', { name: '确认发布' }).click()
  await expect(page.getByText('项目发布成功')).toBeVisible()
  await expect(page.getByText('已冻结只读')).toBeVisible()
  await expect(page.getByRole('button', { name: '保存配置' })).toHaveCount(0)
  expect(publishCount).toBe(1)

  await page.reload()
  await expect(page.getByText('项目已经发布，以下问卷版本、人员快照、关系和任务来源均为冻结只读信息。')).toBeVisible()
  await expect(page.getByText('已冻结只读')).toBeVisible()
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
