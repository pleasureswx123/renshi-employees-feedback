<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getCodeImg } from '@/api/login'
import Cookies from 'js-cookie'
import { encrypt, decrypt } from '@/utils/jsencrypt'
import useUserStore from '@/store/modules/user'

const logo = `${import.meta.env.BASE_URL}favicon.svg`
const userStore = useUserStore()
const route = useRoute()
const router = useRouter()
const loginRef = ref()
const loginForm = ref({ username: '', password: '', rememberMe: false, code: '', uuid: '' })
const loginRules = {
  username: [{ required: true, whitespace: true, trigger: 'blur', message: '请输入账号' }],
  password: [{ required: true, trigger: 'blur', message: '请输入密码' }],
  code: [{ required: true, whitespace: true, trigger: 'blur', message: '请输入验证码' }]
}
const codeUrl = ref('')
const loading = ref(false)
const captchaEnabled = ref(false)
const captchaLoading = ref(false)
const captchaReady = ref(false)
const captchaError = ref(false)
const loginError = ref('')
const register = ref(false)
let active = true

async function getCode() {
  if (!active || captchaLoading.value) return
  captchaLoading.value = true
  captchaReady.value = false
  captchaError.value = false
  loginForm.value.code = ''
  loginForm.value.uuid = ''
  codeUrl.value = ''
  try {
    const res = await getCodeImg()
    if (!active) return
    const enabled = res.captchaEnabled !== false
    if (enabled && (!res.img || !res.uuid)) throw new Error('验证码不完整')
    captchaEnabled.value = enabled
    register.value = res.registerEnabled === true
    codeUrl.value = enabled ? `data:image/gif;base64,${res.img}` : ''
    loginForm.value.uuid = enabled ? res.uuid : ''
    captchaReady.value = true
  } catch {
    if (active) captchaError.value = true
  } finally {
    if (active) captchaLoading.value = false
  }
}

async function handleLogin(event) {
  if (event?.isComposing || loading.value || !captchaReady.value || !active) return
  // 校验前锁定，点击和回车共用一次登录操作。
  loading.value = true
  loginError.value = ''
  const loginPath = route.fullPath
  const { redirect, ...otherQueryParams } = route.query
  try {
    const valid = await loginRef.value.validate().catch(() => false)
    if (!valid || !active || route.fullPath !== loginPath) return
    const credentials = { ...loginForm.value, username: loginForm.value.username.trim() }
    // 保留管理端既有的记住密码能力。
    if (credentials.rememberMe) {
      Cookies.set('username', credentials.username, { expires: 30 })
      Cookies.set('password', encrypt(credentials.password), { expires: 30 })
      Cookies.set('rememberMe', true, { expires: 30 })
    } else {
      Cookies.remove('username')
      Cookies.remove('password')
      Cookies.remove('rememberMe')
    }
    await userStore.login(credentials)
    if (active && route.fullPath === loginPath) {
      await router.push({ path: typeof redirect === 'string' ? redirect : '/', query: otherQueryParams })
    }
  } catch (error) {
    if (!active) return
    loginError.value = error?.message || '登录失败，请检查账号、密码及验证码后重试。'
    if (captchaEnabled.value) await getCode()
  } finally {
    if (active) loading.value = false
  }
}

function getCookie() {
  const username = Cookies.get('username')
  const password = Cookies.get('password')
  const rememberMe = Cookies.get('rememberMe')
  Object.assign(loginForm.value, {
    username: username === undefined ? '' : username,
    password: password === undefined ? '' : decrypt(password) || '',
    rememberMe: rememberMe === 'true'
  })
}

onMounted(() => {
  getCookie()
  getCode()
})
onBeforeUnmount(() => { active = false })
</script>

<template>
  <main class="entry-page">
    <header class="entry-brand">
      <img :src="logo" alt="" />
      <div>
        <strong>员工反馈与 360° 评价平台</strong>
        <p>系统管理端 · 组织与权限</p>
      </div>
    </header>

    <div class="entry-shell">
      <section class="entry-intro" aria-labelledby="platform-title">
        <p class="entry-eyebrow">组织有序 · 协作有方</p>
        <h1 id="platform-title">连接组织与人员，<span>做好评价的准备。</span></h1>
        <p class="entry-description">维护公司组织与账号，为 HR 发起评价、员工参与反馈提供统一的人员与权限基础。</p>
        <ul class="entry-features">
          <li>
            <span class="entry-feature-number" aria-hidden="true">01</span>
            <div><h2>组织与人员</h2><p>维护部门、岗位与用户账号，<br />让参评人员与组织信息保持一致。</p></div>
          </li>
          <li>
            <span class="entry-feature-number" aria-hidden="true">02</span>
            <div><h2>角色与权限</h2><p>配置 HR、参评员工与管理权限，<br />让每个人使用对应的功能与数据。</p></div>
          </li>
        </ul>
        <p class="entry-intro-note">评价项目、我的待办与评价报告，请在评价平台中使用。</p>
      </section>

      <section class="entry-form-panel" aria-labelledby="login-title">
        <div class="entry-form-content">
          <header class="entry-form-heading">
            <span class="entry-form-tag">系统管理</span>
            <h2 id="login-title">登录管理端</h2>
            <p>使用具有管理权限的公司账号登录。</p>
          </header>
          <div v-if="captchaError" class="entry-captcha-error">
            <el-alert title="登录验证加载失败，请重试后登录。" type="error" :closable="false" show-icon />
            <el-button :loading="captchaLoading" :disabled="loading" @click="getCode">重新加载</el-button>
          </div>
          <el-alert v-if="loginError" class="entry-captcha-error" :title="loginError" type="error" :closable="false" show-icon />
          <el-form ref="loginRef" class="entry-form" :model="loginForm" :rules="loginRules" :disabled="loading" label-position="top" size="large">
            <el-form-item label="账号" prop="username">
              <el-input v-model="loginForm.username" name="username" autocomplete="username" placeholder="请输入公司账号" @keyup.enter="handleLogin" />
            </el-form-item>
            <el-form-item label="密码" prop="password">
              <el-input v-model="loginForm.password" name="password" type="password" autocomplete="current-password" placeholder="请输入密码" show-password @keyup.enter="handleLogin" />
            </el-form-item>
            <el-form-item v-if="captchaEnabled" label="验证码" prop="code">
              <div class="entry-captcha">
                <el-input v-model="loginForm.code" name="code" autocomplete="off" placeholder="请输入验证码" :disabled="captchaLoading || !captchaReady" @keyup.enter="handleLogin" />
                <el-button class="entry-captcha-button" aria-label="刷新验证码" :loading="captchaLoading" @click="getCode">
                  <img v-if="codeUrl" :src="codeUrl" alt="验证码" />
                  <span v-else>刷新验证码</span>
                </el-button>
              </div>
            </el-form-item>
            <div class="entry-options">
              <el-checkbox v-model="loginForm.rememberMe">记住密码</el-checkbox>
              <router-link v-if="register" to="/register">立即注册</router-link>
            </div>
            <el-button class="entry-login-button" type="primary" :loading="loading" :disabled="loading || !captchaReady" @click="handleLogin">
              {{ loading ? '登录中…' : captchaLoading ? '正在加载…' : '登录' }}
            </el-button>
          </el-form>
          <div class="entry-help">
            <p>还没有账号或忘记密码？请联系公司管理员。</p>
            <p>参与评价的员工，请使用评价平台入口。</p>
          </div>
        </div>
      </section>
    </div>
    <footer class="entry-footer">员工反馈与 360° 评价平台 · 系统管理端</footer>
  </main>
</template>

<style scoped src="@/assets/styles/login-entry.css"></style>
