<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { getCaptcha } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'
import { usePermissionStore } from '@/stores/permission'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const permissionStore = usePermissionStore()
const formRef = ref()
const captchaEnabled = ref(false)
const captchaImage = ref('')
const form = reactive({ username: '', password: '', code: '', uuid: '' })
const rules = {
  username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
  code: [
    {
      validator: (_rule, value, callback) => {
        if (captchaEnabled.value && !value) callback(new Error('请输入验证码'))
        else callback()
      },
      trigger: 'blur'
    }
  ]
}

async function refreshCaptcha() {
  try {
    const response = await getCaptcha()
    captchaEnabled.value = Boolean(response.captchaEnabled)
    form.uuid = response.uuid || ''
    captchaImage.value = response.img ? `data:image/gif;base64,${response.img}` : ''
  } catch {
    captchaEnabled.value = false
    captchaImage.value = ''
  }
}

async function handleLogin() {
  if (authStore.loading) return
  try {
    await formRef.value.validate()
    await authStore.signIn({ ...form, username: form.username.trim() })
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : ''
    await router.replace(redirect || permissionStore.defaultPath())
  } catch (error) {
    if (error instanceof Error) ElMessage.error(error.message)
    form.code = ''
    if (captchaEnabled.value) await refreshCaptcha()
  }
}

onMounted(refreshCaptcha)
</script>

<template>
  <main class="login-page">
    <section class="login-intro" aria-labelledby="platform-title">
      <p class="intro-kicker">Feedback Workspace</p>
      <h1 id="platform-title">员工反馈与 360° 评价平台</h1>
      <p>复用公司统一账号与权限体系，为 HR 和员工提供各自清晰、受控的评价工作台。</p>
    </section>

    <el-card class="login-card" shadow="always">
      <template #header>
        <div>
          <h2>登录评价平台</h2>
          <p>使用现有 RuoYi 系统账号登录</p>
        </div>
      </template>
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @keyup.enter="handleLogin"
      >
        <el-form-item label="账号" prop="username">
          <el-input v-model="form.username" name="username" autocomplete="username" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            name="password"
            type="password"
            autocomplete="current-password"
            show-password
          />
        </el-form-item>
        <el-form-item v-if="captchaEnabled" label="验证码" prop="code">
          <div class="captcha-row">
            <el-input v-model="form.code" name="code" autocomplete="off" />
            <el-button class="captcha-button" @click="refreshCaptcha">
              <img v-if="captchaImage" :src="captchaImage" alt="点击刷新验证码" />
              <span v-else>刷新验证码</span>
            </el-button>
          </div>
        </el-form-item>
        <el-button
          class="login-button"
          type="primary"
          :loading="authStore.loading"
          :disabled="authStore.loading"
          @click="handleLogin"
        >
          登录
        </el-button>
      </el-form>
    </el-card>
  </main>
</template>

<style scoped>
.login-page {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(360px, 460px);
  align-items: center;
  gap: 72px;
  min-height: 100vh;
  padding: 64px clamp(32px, 8vw, 140px);
  background:
    radial-gradient(circle at 16% 20%, rgb(37 99 235 / 12%), transparent 32%),
    linear-gradient(135deg, #f8fafc, #eef4ff);
}

.login-intro {
  max-width: 680px;
}

.intro-kicker {
  color: #2563eb;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.login-intro h1 {
  margin: 12px 0 20px;
  color: #0f172a;
  font-size: clamp(36px, 5vw, 62px);
  line-height: 1.15;
}

.login-intro p:last-child {
  max-width: 600px;
  color: #475569;
  font-size: 18px;
  line-height: 1.8;
}

.login-card {
  border: 0;
  border-radius: 18px;
}

.login-card h2 {
  margin: 0;
  color: #0f172a;
}

.login-card p {
  margin: 8px 0 0;
  color: #64748b;
}

.login-button {
  width: 100%;
  margin-top: 8px;
}

.captcha-row {
  display: grid;
  grid-template-columns: 1fr 132px;
  gap: 10px;
  width: 100%;
}

.captcha-button {
  height: 32px;
  padding: 0;
  overflow: hidden;
}

.captcha-button img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

@media (max-width: 900px) {
  .login-page {
    grid-template-columns: 1fr;
    gap: 32px;
    padding: 32px 20px;
  }

  .login-intro h1 {
    font-size: 36px;
  }
}
</style>
