import { beforeEach, describe, expect, it, vi } from 'vitest'

const request = vi.fn()
vi.mock('@/utils/request', () => ({ default: request }))

const { getCaptcha, getCurrentUser, login, logout } = await import('@/api/auth')

describe('认证API契约', () => {
  beforeEach(() => request.mockReset())

  it('登录使用现有OAuth2表单接口且不携带旧Token', async () => {
    const credentials = { username: 'demo', password: 'secret', code: '', uuid: '' }
    await login(credentials)

    expect(request).toHaveBeenCalledWith({
      url: '/login',
      method: 'post',
      data: credentials,
      headers: {
        isToken: false,
        repeatSubmit: false,
        'Content-Type': 'application/x-www-form-urlencoded'
      }
    })
  })

  it('当前用户、退出和验证码沿用后端既有路径', async () => {
    await getCurrentUser()
    await logout()
    await getCaptcha()

    expect(request.mock.calls.map(call => call[0].url)).toEqual(['/getInfo', '/logout', '/captchaImage'])
  })
})
