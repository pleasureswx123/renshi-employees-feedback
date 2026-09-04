<template>
  <main class="management-home">
    <el-card shadow="never" class="welcome-card">
      <div class="welcome-content">
        <el-avatar :size="56" :src="userStore.avatar" :icon="UserFilled" />
        <div class="welcome-copy">
          <span class="eyebrow">{{ brand.title }} · {{ brand.description }}</span>
          <h1>你好，{{ userStore.nickName || userStore.name || '管理员' }}</h1>
          <p>维护组织与账号，配置参评权限，为每一轮评价做好准备。</p>
        </div>
        <div v-if="canEnterFeedback" class="platform-action">
          <el-button v-if="feedbackEntry" type="primary" size="large" tag="a"
            :href="feedbackEntry" target="_blank" rel="noopener noreferrer" :icon="Right">
            进入评价平台
          </el-button>
          <el-button v-else type="primary" size="large" disabled>进入评价平台</el-button>
          <span>{{ feedbackEntry ? '发起评价、填写答卷、查看报告' : '评价平台入口暂未配置，请联系管理员' }}</span>
        </div>
      </div>
    </el-card>

    <section aria-labelledby="overview-title">
      <div class="section-heading">
        <div>
          <h2 id="overview-title">组织与权限概览</h2>
          <p>统计当前账号有权查看的数据。</p>
        </div>
        <div class="refresh-action">
          <span v-if="updatedAt" class="updated-time">更新于 {{ updatedTime }}</span>
          <el-button :icon="Refresh" :loading="loading" @click="refreshOverview">刷新概览</el-button>
        </div>
      </div>
      <div class="metrics-grid" :aria-busy="loading">
        <el-card v-for="metric in metrics" :key="metric.key" shadow="never" class="metric-card">
          <div class="metric-heading">
            <h3>{{ metric.label }}</h3>
            <el-icon :size="20" class="metric-icon"><component :is="metric.icon" /></el-icon>
          </div>
          <el-skeleton v-if="loading && checkPermi([metric.permission])" animated class="metric-loading">
            <template #template><el-skeleton-item variant="h1" style="width: 90px; height: 38px" /></template>
          </el-skeleton>
          <el-statistic v-else-if="overview[metric.key].status === 'success'" :value="overview[metric.key].value" />
          <div v-else class="metric-state" :class="{ 'is-error': overview[metric.key].status === 'error' }">
            {{ overviewStateLabels[overview[metric.key].status] }}
          </div>
          <p>{{ metric.hint }}</p>
        </el-card>
      </div>
    </section>

    <div class="home-columns">
      <el-card shadow="never" class="management-card">
        <template #header>
          <div class="card-heading"><h2>常用管理</h2><span>按当前账号权限显示</span></div>
        </template>
        <div class="entry-grid">
          <el-button v-for="entry in availableEntries" :key="entry.path"
            class="entry-button" :aria-label="entry.title" @click="openManagement(entry)">
            <el-icon class="entry-icon" :size="22"><component :is="entry.icon" /></el-icon>
            <span class="entry-copy"><strong>{{ entry.title }}</strong><small>{{ entry.description }}</small></span>
            <el-icon class="entry-arrow"><ArrowRight /></el-icon>
          </el-button>
        </div>
      </el-card>

      <el-card shadow="never" class="guide-card">
        <template #header><h2>开始一轮评价</h2></template>
        <ol class="preparation-list">
          <li><span class="step-number">1</span><div><h3>核对组织与人员</h3><p>确认部门归属、真实姓名和账号启用状态。</p></div></li>
          <li><span class="step-number">2</span><div><h3>分配参评权限</h3><p>员工分配参评角色；需要参评的 HR 同时具有 HR 和员工角色。</p></div></li>
          <li><span class="step-number">3</span><div><h3>进入评价平台</h3><p>由 HR 配置问卷与评价关系、发布项目，再由员工登录填写。</p></div></li>
        </ol>
        <div class="guide-note"><el-icon><InfoFilled /></el-icon><span>原始答案为独立权限，请按实际需要授权。</span></div>
      </el-card>
    </div>
  </main>
</template>

<script setup>
import { computed, onActivated, onBeforeUnmount, onDeactivated, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, Briefcase, Connection, Document, InfoFilled, Lock, Refresh, Right, User, UserFilled } from '@element-plus/icons-vue'
import { listUser } from '@/api/system/user'
import { listDept } from '@/api/system/dept'
import { listRole } from '@/api/system/role'
import useUserStore from '@/store/modules/user'
import { brand } from '@/config/brand'
import { checkPermi } from '@/utils/permission'
import { emptyOverview, loadManagementOverview, overviewPermissions, resolveFeedbackEntry } from '@/utils/managementOverview'

defineOptions({ name: 'Index' })

const router = useRouter()
const userStore = useUserStore()
const loading = ref(false)
const overview = reactive(emptyOverview())
const updatedAt = ref(null)
const feedbackEntry = resolveFeedbackEntry(import.meta.env.VITE_FEEDBACK_APP_URL)
const canEnterFeedback = computed(() => checkPermi([
  'feedback:project:list', 'feedback:progress:view', 'feedback:report:view',
  'feedback:answer:view', 'feedback:task:view', 'feedback:history:view'
]))
const contextKey = computed(() => JSON.stringify([
  userStore.id, [...userStore.permissions].sort(), [...userStore.roles].sort()
]))
const updatedTime = computed(() => updatedAt.value
  ? new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }).format(updatedAt.value)
  : '')
const overviewStateLabels = { idle: '待刷新', forbidden: '无查看权限', error: '读取失败，请刷新重试' }
const metrics = [
  { key: 'users', label: '账号总数', permission: overviewPermissions.users, icon: User, hint: '包含管理员及测试账号' },
  { key: 'departments', label: '组织部门', permission: overviewPermissions.departments, icon: Connection, hint: '包含公司、部门与下级团队' },
  { key: 'roles', label: '授权角色', permission: overviewPermissions.roles, icon: Lock, hint: '已建立的系统角色' }
]
const entries = [
  { title: '用户管理', description: '维护姓名、部门与账号状态', path: '/system/user', permission: 'system:user:list', icon: User },
  { title: '部门管理', description: '维护公司、部门与团队结构', path: '/system/dept', permission: 'system:dept:list', icon: Connection },
  { title: '角色授权', description: '配置菜单权限与数据范围', path: '/system/role', permission: 'system:role:list', icon: Lock },
  { title: '岗位管理', description: '维护组织岗位信息', path: '/system/post', permission: 'system:post:list', icon: Briefcase },
  { title: '操作日志', description: '查看系统操作与审计记录', path: '/monitor/operlog', permission: 'monitor:operlog:list', icon: Document },
  { title: '个人中心', description: '维护个人资料与登录密码', path: '/user/profile', icon: UserFilled }
]
const availableEntries = computed(() => entries.filter(entry => {
  if (!entry.permission) return true
  return checkPermi([entry.permission]) && router.getRoutes().some(route => route.path === entry.path)
}))

let requestSequence = 0
let viewActive = true

async function refreshOverview() {
  if (loading.value || !viewActive) return
  loading.value = true
  const requestId = ++requestSequence
  const context = contextKey.value
  const result = await loadManagementOverview(permission => checkPermi([permission]), {
    users: listUser, departments: listDept, roles: listRole
  })
  // 离开页面、切换账号或变更权限后，旧请求不得回填当前概览。
  if (requestId !== requestSequence || context !== contextKey.value || !viewActive) return
  Object.assign(overview, result)
  updatedAt.value = Object.values(result).some(item => item.status === 'success') ? new Date() : null
  loading.value = false
}

function openManagement(entry) {
  if (entry.permission && !checkPermi([entry.permission])) return
  router.push(entry.path)
}

function invalidatePending() {
  requestSequence += 1
  loading.value = false
}

watch(contextKey, () => {
  invalidatePending()
  Object.assign(overview, emptyOverview())
  updatedAt.value = null
  void refreshOverview()
}, { immediate: true })

onActivated(() => {
  viewActive = true
  if (!loading.value) void refreshOverview()
})
onDeactivated(() => {
  viewActive = false
  invalidatePending()
})
onBeforeUnmount(() => {
  viewActive = false
  invalidatePending()
})
</script>

<style scoped lang="scss">
.management-home {
  padding: 24px;
  color: var(--el-text-color-primary);
  background: var(--el-bg-color-page);
  min-height: calc(100vh - 90px);
}
.management-home h1, .management-home h2, .management-home h3, .management-home p { margin: 0; }
.management-home h2 { font-size: 17px; font-weight: 600; }
.management-home :deep(.el-card) { border-radius: 12px; }
.welcome-card { background: linear-gradient(110deg, var(--el-bg-color), var(--el-color-primary-light-9)); }
.welcome-content { display: flex; align-items: center; gap: 18px; padding: 8px; }
.welcome-content > .el-avatar { flex-shrink: 0; }
.welcome-copy { flex: 1; min-width: 0; }
.eyebrow { font-size: 12px; color: var(--el-color-primary); }
.welcome-copy h1 { margin: 8px 0; font-size: 25px; line-height: 1.4; overflow-wrap: anywhere; }
.welcome-copy p, .platform-action > span { color: var(--el-text-color-secondary); font-size: 13px; line-height: 1.7; }
.platform-action { display: flex; flex-direction: column; gap: 8px; align-items: flex-end; }
.platform-action .el-button { text-decoration: none; }
.section-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin: 26px 0 14px; }
.section-heading p { margin-top: 6px; color: var(--el-text-color-secondary); font-size: 13px; }
.refresh-action { display: flex; align-items: center; gap: 12px; }
.updated-time { color: var(--el-text-color-secondary); font-size: 12px; white-space: nowrap; }
.metrics-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
.metric-heading { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 14px; }
.metric-heading h3 { font-size: 14px; font-weight: 500; color: var(--el-text-color-regular); }
.metric-icon { color: var(--el-color-primary); }
.metric-card :deep(.el-statistic__content) { font-size: 32px; font-weight: 600; line-height: 40px; }
.metric-state, .metric-loading { min-height: 40px; display: flex; align-items: center; color: var(--el-text-color-secondary); font-size: 15px; }
.metric-state.is-error { color: var(--el-color-danger); }
.metric-card p { margin-top: 10px; font-size: 12px; line-height: 1.6; color: var(--el-text-color-secondary); }
.home-columns { display: grid; grid-template-columns: minmax(0, 1.6fr) minmax(290px, 1fr); gap: 20px; margin-top: 22px; align-items: start; }
.card-heading { display: flex; justify-content: space-between; align-items: center; gap: 10px; }
.card-heading > span { font-size: 12px; color: var(--el-text-color-secondary); }
.entry-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.entry-button { width: 100%; height: auto; min-height: 86px; margin: 0 !important; padding: 16px; text-align: left; border-radius: 9px; white-space: normal; }
.entry-button :deep(> span) { display: flex; align-items: center; gap: 12px; width: 100%; min-width: 0; }
.entry-icon { flex-shrink: 0; color: var(--el-color-primary); }
.entry-copy { display: flex; flex-direction: column; gap: 7px; flex: 1; min-width: 0; line-height: 1.5; }
.entry-copy strong { font-size: 14px; font-weight: 600; }
.entry-copy small { color: var(--el-text-color-secondary); font-size: 12px; overflow-wrap: anywhere; }
.entry-arrow { flex-shrink: 0; color: var(--el-text-color-placeholder); }
.preparation-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 22px; }
.preparation-list li { display: flex; align-items: flex-start; gap: 12px; }
.step-number { display: grid; place-items: center; width: 28px; height: 28px; flex-shrink: 0; border-radius: 50%; color: var(--el-color-primary); background: var(--el-color-primary-light-9); font-size: 13px; font-weight: 600; }
.preparation-list h3 { margin: 3px 0 6px; font-size: 14px; }
.preparation-list p { color: var(--el-text-color-secondary); font-size: 13px; line-height: 1.7; }
.guide-note { display: flex; align-items: flex-start; gap: 8px; margin-top: 24px; padding-top: 18px; border-top: 1px solid var(--el-border-color-lighter); font-size: 12px; line-height: 1.7; color: var(--el-text-color-secondary); }
.guide-note .el-icon { margin-top: 3px; flex-shrink: 0; color: var(--el-color-primary); }
@media (max-width: 1200px) {
  .home-columns { grid-template-columns: 1fr; }
}
@media (max-width: 768px) {
  .management-home { padding: 16px; }
  .welcome-content { flex-wrap: wrap; padding: 0; gap: 12px; }
  .welcome-copy { flex-basis: calc(100% - 68px); }
  .welcome-copy h1 { font-size: 21px; }
  .platform-action { width: 100%; align-items: stretch; margin-top: 6px; }
  .section-heading { align-items: flex-start; flex-wrap: wrap; }
  .refresh-action { width: 100%; justify-content: space-between; }
  .metrics-grid { grid-template-columns: 1fr; gap: 12px; }
  .entry-grid { grid-template-columns: 1fr; }
  .card-heading { align-items: flex-start; flex-direction: column; }
}
</style>
