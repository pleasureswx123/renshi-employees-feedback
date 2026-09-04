import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import LoginView from '@/views/auth/LoginView.vue'

const mocks = vi.hoisted(() => ({
  getCaptcha: vi.fn(),
  signIn: vi.fn(),
  replace: vi.fn(),
  defaultPath: vi.fn(),
  route: { fullPath: '/login', query: {} }
}))
vi.mock('@/api/auth', () => ({ getCaptcha: mocks.getCaptcha }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ signIn: mocks.signIn, loading: false }) }))
vi.mock('@/stores/permission', () => ({ usePermissionStore: () => ({ defaultPath: mocks.defaultPath }) }))
vi.mock('vue-router', () => ({ useRoute: () => mocks.route, useRouter: () => ({ replace: mocks.replace }) }))

const captcha = { captchaEnabled: true, img: 'test-image', uuid: 'captcha-1' }
let wrapper
const loginButton = () => wrapper.get('.entry-login-button')
async function openLogin() {
  wrapper = mount(LoginView, { global: { plugins: [ElementPlus] } })
  await flushPromises()
}
async function fillCredentials() {
  await wrapper.get('input[name="username"]').setValue(' employee ')
  await wrapper.get('input[name="password"]').setValue('test-password')
  if (wrapper.find('input[name="code"]').exists()) await wrapper.get('input[name="code"]').setValue('test-code')
}

describe('评价平台登录表单', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    mocks.route.fullPath = '/login'
    mocks.route.query = {}
    mocks.getCaptcha.mockResolvedValue(captcha)
    mocks.signIn.mockResolvedValue()
    mocks.replace.mockResolvedValue()
    mocks.defaultPath.mockReturnValue('/employee/todos')
  })
  afterEach(() => wrapper?.unmount())

  it('真实 Element Plus 校验拦截空表单，不发送登录或更换验证码', async () => {
    await openLogin()
    await loginButton().trigger('click')
    await flushPromises()
    await vi.waitFor(() => {
      expect(wrapper.text()).toContain('请输入账号')
      expect(wrapper.text()).toContain('请输入密码')
      expect(wrapper.text()).toContain('请输入验证码')
    })
    expect(mocks.signIn).not.toHaveBeenCalled()
    expect(mocks.getCaptcha).toHaveBeenCalledTimes(1)
    expect(loginButton().element.disabled).toBe(false)
  })

  it('校验和请求期间阻止重复登录，按权限进入工作台', async () => {
    let finishLogin
    mocks.signIn.mockImplementation(() => new Promise(resolve => { finishLogin = resolve }))
    await openLogin()
    await fillCredentials()
    const click = loginButton().trigger('click')
    const enter = wrapper.get('input[name="password"]').trigger('keyup', { key: 'Enter' })
    await Promise.all([click, enter])
    await flushPromises()
    expect(mocks.signIn).toHaveBeenCalledTimes(1)
    expect(mocks.signIn).toHaveBeenCalledWith({
      username: 'employee', password: 'test-password', code: 'test-code', uuid: 'captcha-1'
    })
    expect(loginButton().element.disabled).toBe(true)
    expect(wrapper.get('input[name="username"]').element.disabled).toBe(true)
    expect(mocks.replace).not.toHaveBeenCalled()
    finishLogin()
    await flushPromises()
    expect(mocks.replace).toHaveBeenCalledWith('/employee/todos')
  })

  it('关闭验证码时支持回车登录并恢复目标路由', async () => {
    mocks.getCaptcha.mockResolvedValue({ captchaEnabled: false })
    mocks.route.query = { redirect: '/hr/projects' }
    await openLogin()
    await fillCredentials()
    await wrapper.get('input[name="password"]').trigger('keyup', { key: 'Enter' })
    await flushPromises()
    expect(wrapper.find('input[name="code"]').exists()).toBe(false)
    expect(mocks.signIn).toHaveBeenCalledTimes(1)
    expect(mocks.replace).toHaveBeenCalledWith('/hr/projects')
  })

  it('登录失败保留账号，清空旧验证码并允许重试', async () => {
    mocks.signIn.mockRejectedValueOnce(new Error('账号或密码不正确'))
    mocks.getCaptcha.mockResolvedValueOnce(captcha).mockResolvedValue({ ...captcha, uuid: 'captcha-2' })
    await openLogin()
    await fillCredentials()
    await loginButton().trigger('click')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('账号或密码不正确')
    expect(wrapper.get('input[name="username"]').element.value).toBe(' employee ')
    expect(wrapper.get('input[name="code"]').element.value).toBe('')
    expect(loginButton().element.disabled).toBe(false)
    await wrapper.get('input[name="code"]').setValue('new-code')
    await loginButton().trigger('click')
    await flushPromises()
    expect(mocks.signIn.mock.calls[1][0]).toMatchObject({ code: 'new-code', uuid: 'captcha-2' })
    expect(mocks.replace).toHaveBeenCalledTimes(1)
  })

  it.each([
    ['请求失败', () => Promise.reject(new Error('连接失败'))],
    ['验证码缺失', () => Promise.resolve({ captchaEnabled: true })]
  ])('验证码%s时阻止登录，重新加载后恢复', async (_name, response) => {
    mocks.getCaptcha.mockImplementationOnce(response)
    await openLogin()
    expect(wrapper.text()).toContain('登录验证加载失败')
    expect(loginButton().element.disabled).toBe(true)
    await wrapper.get('.entry-captcha-error button').trigger('click')
    await flushPromises()
    expect(loginButton().element.disabled).toBe(false)
    expect(wrapper.text()).not.toContain('登录验证加载失败')
  })

  it('验证码刷新期间不允许提交，并清空上一张验证码输入', async () => {
    let finishCaptcha
    await openLogin()
    await fillCredentials()
    mocks.getCaptcha.mockImplementationOnce(() => new Promise(resolve => { finishCaptcha = resolve }))
    await wrapper.get('[aria-label="刷新验证码"]').trigger('click')
    expect(loginButton().element.disabled).toBe(true)
    expect(wrapper.get('input[name="code"]').element.value).toBe('')
    await wrapper.get('input[name="password"]').trigger('keyup', { key: 'Enter' })
    expect(mocks.signIn).not.toHaveBeenCalled()
    finishCaptcha({ ...captcha, uuid: 'captcha-refreshed' })
    await flushPromises()
    expect(loginButton().element.disabled).toBe(false)
  })

  it('离开页面后，迟到的登录结果不能触发跳转', async () => {
    let finishLogin
    mocks.signIn.mockImplementationOnce(() => new Promise(resolve => { finishLogin = resolve }))
    await openLogin()
    await fillCredentials()
    await loginButton().trigger('click')
    await flushPromises()
    wrapper.unmount()
    finishLogin()
    await flushPromises()
    expect(mocks.replace).not.toHaveBeenCalled()
  })
})
