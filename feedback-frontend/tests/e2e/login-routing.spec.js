import { expect, test } from '@playwright/test'

const userInfo = {
  code: 200,
  msg: '操作成功',
  user: { userId: 2, userName: 'feedback-user', nickName: '评价用户' },
  roles: ['feedback_hr', 'feedback_employee'],
  permissions: [
    'feedback:project:list',
    'feedback:project:add',
    'feedback:project:edit',
    'feedback:project:remove',
    'feedback:questionnaire:edit',
    'feedback:task:view',
    'feedback:history:view'
  ]
}

async function mockPublicEndpoints(page) {
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
  await page.route('**/dev-api/feedback/projects*', route =>
    route.fulfill({
      json: {
        code: 200,
        rows: [],
        pageNum: 1,
        pageSize: 10,
        total: 0,
        hasNext: false
      }
    })
  )
}

test('登录、刷新恢复、双工作台切换和退出形成完整路由链', async ({ page }) => {
  let getInfoCount = 0
  await mockPublicEndpoints(page)
  await page.route('**/dev-api/login', route => route.fulfill({ json: { code: 200, token: 'e2e-token' } }))
  await page.route('**/dev-api/getInfo', route => {
    getInfoCount += 1
    return route.fulfill({ json: userInfo })
  })
  await page.route('**/dev-api/logout', route => route.fulfill({ json: { code: 200, msg: '退出成功' } }))

  await page.goto('/login')
  await page.getByLabel('账号').fill('feedback-user')
  await page.getByLabel('密码').fill('secret')
  await page.getByRole('button', { name: '登录', exact: true }).click()

  await expect(page).toHaveURL(/\/hr\/projects$/)
  await expect(page.getByRole('heading', { name: '评价项目' })).toBeVisible()

  await page.reload()
  await expect(page.getByRole('heading', { name: '评价项目' })).toBeVisible()
  expect(getInfoCount).toBeGreaterThanOrEqual(2)

  await page.getByRole('button', { name: '员工工作台' }).click()
  await expect(page).toHaveURL(/\/employee\/todos$/)
  await expect(page.getByRole('heading', { name: '我的待办' })).toBeVisible()

  await page.getByRole('button', { name: '退出登录' }).click()
  await expect(page).toHaveURL(/\/login$/)
})

test('失效Token刷新受保护路由后返回登录页', async ({ context, page }) => {
  await mockPublicEndpoints(page)
  await page.route('**/dev-api/getInfo', route =>
    route.fulfill({ json: { code: 401, msg: '登录状态已失效' } })
  )
  await context.addCookies([
    { name: 'Feedback-Token', value: 'expired-token', url: 'http://127.0.0.1:5176' }
  ])

  await page.goto('/employee/todos')

  await expect(page).toHaveURL(/\/login\?redirect=/)
  await expect(page.getByRole('heading', { name: '登录评价平台' })).toBeVisible()
})

test('员工单权限账号不能看到或直接访问HR工作台', async ({ page }) => {
  await mockPublicEndpoints(page)
  await page.route('**/dev-api/login', route => route.fulfill({ json: { code: 200, token: 'employee-token' } }))
  await page.route('**/dev-api/getInfo', route =>
    route.fulfill({
      json: {
        ...userInfo,
        roles: ['feedback_employee'],
        permissions: ['feedback:task:view', 'feedback:history:view']
      }
    })
  )

  await page.goto('/login')
  await page.getByLabel('账号').fill('employee-user')
  await page.getByLabel('密码').fill('secret')
  await page.getByRole('button', { name: '登录', exact: true }).click()

  await expect(page).toHaveURL(/\/employee\/todos$/)
  await expect(page.getByRole('button', { name: 'HR 工作台' })).toHaveCount(0)

  await page.goto('/hr/projects')
  await expect(page).toHaveURL(/\/403$/)
  await expect(page.getByText('暂无评价平台权限')).toBeVisible()
})
