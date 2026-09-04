<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BriefcaseIcon from '@iconify-vue/lucide/briefcase-business'
import MessagesIcon from '@iconify-vue/lucide/messages-square'
import LockIcon from '@iconify-vue/lucide/lock-keyhole'
import UserIcon from '@iconify-vue/lucide/user-round'
import ArrowIcon from '@iconify-vue/lucide/arrow-right'

import { getCaptcha } from '@/api/auth'
import loginBackground from '@/assets/login/feedback-background.webp'
import loginBackgroundCompact from '@/assets/login/feedback-background-compact.webp'
import { brand } from '@/config/brand'
import { useAuthStore } from '@/stores/auth'
import { usePermissionStore } from '@/stores/permission'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const permissionStore = usePermissionStore()
const formRef = ref()
const submitting = ref(false)
const busy = computed(() => submitting.value || authStore.loading)
const captchaEnabled = ref(false)
const captchaImage = ref('')
const captchaLoading = ref(false)
const captchaReady = ref(false)
const captchaError = ref(false)
const loginError = ref('')
let active = true
const form = reactive({ username: '', password: '', code: '', uuid: '' })
const rules = {
  username: [{ required: true, whitespace: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
  code: [{ required: true, whitespace: true, message: '请输入验证码', trigger: 'blur' }]
}

async function refreshCaptcha() {
  if (!active || captchaLoading.value) return
  captchaLoading.value = true
  captchaReady.value = false
  captchaError.value = false
  form.code = ''
  form.uuid = ''
  captchaImage.value = ''
  try {
    const response = await getCaptcha()
    if (!active) return
    const enabled = response.captchaEnabled !== false
    if (enabled && (!response.img || !response.uuid)) throw new Error('验证码不完整')
    captchaEnabled.value = enabled
    form.uuid = enabled ? response.uuid : ''
    captchaImage.value = enabled ? `data:image/gif;base64,${response.img}` : ''
    captchaReady.value = true
  } catch {
    if (active) captchaError.value = true
  } finally {
    if (active) captchaLoading.value = false
  }
}

async function handleLogin(event) {
  if (event?.isComposing || busy.value || !captchaReady.value || !active) return
  // 校验前锁定，避免点击和回车同时进入登录链路。
  submitting.value = true
  loginError.value = ''
  const loginPath = route.fullPath
  const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : ''
  try {
    const valid = await formRef.value.validate().catch(() => false)
    if (!valid || !active || route.fullPath !== loginPath) return
    await authStore.signIn({ ...form, username: form.username.trim() })
    if (active && route.fullPath === loginPath) {
      await router.replace(redirect || permissionStore.defaultPath())
    }
  } catch (error) {
    if (!active) return
    loginError.value = error?.message || '登录失败，请稍后重试'
    if (captchaEnabled.value) await refreshCaptcha()
  } finally {
    if (active) submitting.value = false
  }
}

onMounted(refreshCaptcha)
onBeforeUnmount(() => { active = false })
</script>

<template>
  <main class="entry-page">
    <picture class="entry-background" aria-hidden="true">
      <source media="(max-width: 900px)" :srcset="loginBackgroundCompact" />
      <img :src="loginBackground" alt="" fetchpriority="high" decoding="async" />
    </picture>
    <div class="entry-shade" aria-hidden="true"></div>
    <header class="entry-brand">
      <img class="entry-company-logo" :src="brand.companyLogo" :alt="brand.companyName" width="1231" height="267" />
      <div class="entry-product-brand">
        <img :src="brand.logo" alt="" />
        <div>
          <strong>{{ brand.name }}<span class="entry-brand-edition">{{ brand.edition }}</span></strong>
          <p>{{ brand.description }}</p>
        </div>
      </div>
    </header>

    <div class="entry-shell">
      <section class="entry-intro" aria-labelledby="platform-title">
        <p class="entry-eyebrow">{{ brand.tagline }}</p>
        <h1 id="platform-title">让每一次反馈，<span>成为成长的起点。</span></h1>
        <p class="entry-description">从发起评价到完成反馈，让团队协作有依据，让个人成长有方向。</p>
        <ul class="entry-features">
          <li>
            <BriefcaseIcon class="entry-feature-icon" aria-hidden="true" />
            <div><h2>HR 工作台</h2><p>发起评价 · 跟进进度 · 查看报告</p></div>
          </li>
          <li>
            <MessagesIcon class="entry-feature-icon" aria-hidden="true" />
            <div><h2>员工工作台</h2><p>填写评价 · 暂存答卷 · 查看记录</p></div>
          </li>
        </ul>
      </section>

      <section class="entry-form-panel" aria-labelledby="login-title">
        <div class="entry-form-content">
          <header class="entry-form-heading">
            <span class="entry-form-tag"><LockIcon aria-hidden="true" />公司账号登录</span>
            <h2 id="login-title">登录评价平台</h2>
            <p>使用公司分配的账号，进入你的工作台。</p>
          </header>
          <div v-if="captchaError" class="entry-captcha-error">
            <el-alert title="登录验证加载失败，请重试后登录。" type="error" :closable="false" show-icon />
            <el-button :loading="captchaLoading" :disabled="busy" @click="refreshCaptcha">重新加载</el-button>
          </div>
          <el-alert v-if="loginError" class="entry-captcha-error" :title="loginError" type="error" :closable="false" show-icon />
          <el-form ref="formRef" class="entry-form" :model="form" :rules="rules" :disabled="busy" label-position="top" size="large">
            <el-form-item label="账号" prop="username">
              <el-input v-model="form.username" :prefix-icon="UserIcon" name="username" autocomplete="username" placeholder="请输入公司账号" @keyup.enter="handleLogin" />
            </el-form-item>
            <el-form-item label="密码" prop="password">
              <el-input v-model="form.password" :prefix-icon="LockIcon" name="password" type="password" autocomplete="current-password" placeholder="请输入密码" show-password @keyup.enter="handleLogin" />
            </el-form-item>
            <el-form-item v-if="captchaEnabled" label="验证码" prop="code">
              <div class="entry-captcha">
                <el-input v-model="form.code" name="code" autocomplete="off" placeholder="请输入验证码" :disabled="captchaLoading || !captchaReady" @keyup.enter="handleLogin" />
                <el-button class="entry-captcha-button" aria-label="刷新验证码" :loading="captchaLoading" @click="refreshCaptcha">
                  <img v-if="captchaImage" :src="captchaImage" alt="验证码" />
                  <span v-else>刷新验证码</span>
                </el-button>
              </div>
            </el-form-item>
            <el-button class="entry-login-button" type="primary" :loading="busy" :disabled="busy || !captchaReady" @click="handleLogin">
              {{ busy ? '登录中…' : captchaLoading ? '正在加载…' : '登录' }}
              <ArrowIcon v-if="!busy && !captchaLoading" class="entry-login-arrow" aria-hidden="true" />
            </el-button>
          </el-form>
          <div class="entry-help">
            <p>还没有账号或忘记密码？请联系公司管理员。</p>
            <p>登录后未看到评价任务，请联系 HR 确认参评安排。</p>
          </div>
        </div>
      </section>
    </div>
    <footer class="entry-footer"><span>{{ brand.title }} · HR 与员工工作台</span><span>{{ brand.tagline }}</span></footer>
  </main>
</template>

<style scoped src="@/styles/login-entry.css"></style>
