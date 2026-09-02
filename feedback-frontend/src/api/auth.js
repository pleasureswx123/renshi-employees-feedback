import request from '@/utils/request'

export function login(credentials) {
  return request({
    url: '/login',
    method: 'post',
    data: credentials,
    headers: {
      isToken: false,
      repeatSubmit: false,
      'Content-Type': 'application/x-www-form-urlencoded'
    }
  })
}

export function getCurrentUser() {
  return request({ url: '/getInfo', method: 'get' })
}

export function logout() {
  return request({ url: '/logout', method: 'post', headers: { repeatSubmit: false } })
}

export function getCaptcha() {
  return request({
    url: '/captchaImage',
    method: 'get',
    timeout: 20000,
    headers: { isToken: false, encrypt: false, encryptResponse: false }
  })
}
