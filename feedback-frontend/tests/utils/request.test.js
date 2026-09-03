import { beforeEach, describe, expect, it, vi } from 'vitest'

const transport = vi.hoisted(() => ({
  decryptTransportErrorResponse: vi.fn(async error => error),
  decryptTransportResponse: vi.fn(async response => response),
  encryptTransportRequest: vi.fn(async config => config),
  invalidateTransportKeyMeta: vi.fn(),
  resetTransportRequestConfig: vi.fn(config => config),
  shouldRetryTransportWithFreshKey: vi.fn(() => false)
}))
const message = vi.hoisted(() => ({ error: vi.fn() }))

vi.mock('@/utils/transportCrypto', () => transport)
vi.mock('@/utils/auth', () => ({ getToken: vi.fn(() => ''), removeToken: vi.fn() }))
vi.mock('element-plus', () => ({ ElMessage: message }))

const request = (await import('@/utils/request')).default

function successAdapter(payload = { code: 200, data: {} }) {
  return vi.fn(async config => ({
    data: payload,
    status: 200,
    statusText: 'OK',
    headers: {},
    config
  }))
}

function rejectedAdapter(factory) {
  return vi.fn(async config => {
    throw factory(config)
  })
}

describe('请求错误机器分类', () => {
  beforeEach(() => {
    Object.values(transport).forEach(fn => fn.mockClear())
    transport.decryptTransportErrorResponse.mockImplementation(async error => error)
    transport.decryptTransportResponse.mockImplementation(async response => response)
    transport.encryptTransportRequest.mockImplementation(async config => config)
    transport.resetTransportRequestConfig.mockImplementation(config => config)
    transport.shouldRetryTransportWithFreshKey.mockReturnValue(false)
    message.error.mockClear()
  })

  it('重复写请求在适配器发送前标记为DUPLICATE_MUTATION', async () => {
    const adapter = successAdapter()
    const config = { adapter, headers: { repeatInterval: 3000 } }
    await request.post('/request-test/duplicate', { projectId: 12 }, config)

    await expect(request.post('/request-test/duplicate', { projectId: 12 }, config)).rejects.toMatchObject({
      kind: 'DUPLICATE_MUTATION',
      requestSent: false,
      status: 0
    })
    expect(adapter).toHaveBeenCalledTimes(1)
  })

  it('传输加密前置失败保留REQUEST_SETUP且明确请求未发出', async () => {
    const adapter = successAdapter()
    transport.encryptTransportRequest.mockRejectedValueOnce(new Error('传输加密失败'))

    await expect(request.post('/request-test/encryption', { projectId: 12 }, { adapter })).rejects.toMatchObject({
      kind: 'REQUEST_SETUP',
      requestSent: false,
      status: 0
    })
    expect(adapter).not.toHaveBeenCalled()
  })

  it('传输前置失败会释放本地防重记录并允许立即重新发送', async () => {
    const adapter = successAdapter()
    transport.encryptTransportRequest.mockRejectedValueOnce(new Error('传输加密失败'))
    await expect(request.post('/request-test/setup-retry', { projectId: 12 }, { adapter })).rejects.toMatchObject({
      kind: 'REQUEST_SETUP',
      requestSent: false
    })

    await expect(request.post('/request-test/setup-retry', { projectId: 12 }, { adapter })).resolves.toEqual({
      code: 200,
      data: {}
    })
    expect(adapter).toHaveBeenCalledTimes(1)
  })

  it.each([
    ['TIMEOUT', 0, config => Object.assign(new Error('timeout'), { code: 'ECONNABORTED', config })],
    ['NETWORK', 0, config => Object.assign(new Error('Network Error'), { code: 'ERR_NETWORK', config, request: {} })],
    ['HTTP_SERVER', 503, config => Object.assign(new Error('Request failed'), {
      config,
      response: { status: 503, data: { code: 503, msg: '网关不可用' }, headers: {}, config }
    })]
  ])('适配器已经启动后的错误标记为%s且requestSent=true', async (kind, status, factory) => {
    const adapter = rejectedAdapter(factory)

    await expect(request.post(`/request-test/${kind}`, { projectId: 12 }, { adapter })).rejects.toMatchObject({
      kind,
      requestSent: true,
      status
    })
    expect(adapter).toHaveBeenCalledTimes(1)
  })

  it('HTTP4xx保留HTTP_CLIENT分类而不是服务端结果未知分类', async () => {
    const adapter = rejectedAdapter(config => Object.assign(new Error('Request failed'), {
      config,
      response: {
        status: 422,
        data: { code: 422, msg: '参数错误', data: { code: 'VALIDATION_ERROR' } },
        headers: {},
        config
      }
    }))

    await expect(request.post('/request-test/client-error', { projectId: 12 }, { adapter })).rejects.toMatchObject({
      kind: 'HTTP_CLIENT',
      requestSent: true,
      status: 422,
      data: { code: 'VALIDATION_ERROR' }
    })
  })

  it('受页面epoch管理的请求可抑制全局错误提示并保留机器错误', async () => {
    const adapter = rejectedAdapter(config => Object.assign(new Error('Request failed'), {
      config,
      response: {
        status: 503,
        data: { code: 503, msg: '旧请求失败' },
        headers: {},
        config
      }
    }))

    await expect(request.get('/request-test/stale', {
      adapter,
      suppressErrorMessage: true
    })).rejects.toMatchObject({
      kind: 'HTTP_SERVER',
      requestSent: true,
      status: 503
    })
    expect(message.error).not.toHaveBeenCalled()
  })

  it('响应解密失败保留RESPONSE_PROCESSING且明确请求已经发出', async () => {
    transport.decryptTransportResponse.mockRejectedValueOnce(new Error('响应解密失败'))

    await expect(request.post('/request-test/response-decryption', { projectId: 12 }, {
      adapter: successAdapter()
    })).rejects.toMatchObject({
      kind: 'RESPONSE_PROCESSING',
      requestSent: true,
      status: 200
    })
  })
})
