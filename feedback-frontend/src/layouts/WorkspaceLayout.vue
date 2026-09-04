<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import WorkspaceIcon from '@/components/WorkspaceIcon.vue'
import WorkspaceNavigation from '@/components/WorkspaceNavigation.vue'
import WorkspaceSwitcher from '@/components/WorkspaceSwitcher.vue'
import { useAuthStore } from '@/stores/auth'
import { usePermissionStore } from '@/stores/permission'
import { useWorkspaceUiStore } from '@/stores/workspaceUi'
import { activeWorkspaceMenu, workspaceMenuItems } from '@/utils/workspaceNavigation'

const props = defineProps({
  workspace: { type: String, required: true },
  title: { type: String, required: true }
})
const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const permissionStore = usePermissionStore()
const ui = useWorkspaceUiStore()
const loggingOut = ref(false)
const mobileNavigationOpen = ref(false)
const logo = `${import.meta.env.BASE_URL}favicon.svg`
const workspaces = computed(() => permissionStore.availableWorkspaces())
const menuItems = computed(() => workspaceMenuItems(props.workspace, permissionStore.hasPermission))
const activeItem = computed(() => activeWorkspaceMenu(route, menuItems.value))
const workspaceHome = computed(() => workspaces.value.find(item => item.key === props.workspace)?.path || '/403')
const pageTitle = computed(() => route.meta.title || props.title)
const userInitial = computed(() => authStore.displayName?.slice(0, 1) || '员')
let compactQuery
function updateCompactLayout() {
  ui.compact = compactQuery.matches
  if (!ui.compact) mobileNavigationOpen.value = false
}
onMounted(() => {
  compactQuery = window.matchMedia('(max-width: 760px)')
  updateCompactLayout()
  compactQuery.addEventListener('change', updateCompactLayout)
})
onBeforeUnmount(() => compactQuery?.removeEventListener('change', updateCompactLayout))

watch(() => route.fullPath, () => { mobileNavigationOpen.value = false })

async function switchWorkspace(workspace) {
  await router.push(workspace.path)
}
async function handleLogout() {
  if (loggingOut.value) return
  loggingOut.value = true
  try {
    await authStore.signOut()
    await router.replace({ name: 'login' })
  } finally {
    loggingOut.value = false
  }
}
</script>

<template>
  <div class="workspace-layout" :class="{ 'is-collapsed': ui.collapsed }">
    <aside class="workspace-aside" aria-label="工作台导航">
      <router-link class="workspace-brand" :to="workspaceHome" title="员工评价平台" aria-label="员工评价平台">
        <img :src="logo" alt="" />
        <strong v-if="!ui.collapsed">员工评价平台</strong>
      </router-link>
      <p v-if="!ui.collapsed" class="workspace-category">{{ title }}</p>
      <WorkspaceNavigation :items="menuItems" :active="activeItem?.path" :collapsed="ui.collapsed" />
      <p v-if="!ui.collapsed" class="sidebar-footer">员工反馈与 360° 评价</p>
    </aside>

    <div class="workspace-body">
      <header class="workspace-header">
        <div class="header-navigation">
          <el-button text class="desktop-navigation-toggle" :aria-label="ui.collapsed ? '展开侧栏' : '收起侧栏'" :aria-expanded="!ui.collapsed" @click="ui.toggleSidebar">
            <WorkspaceIcon :name="ui.collapsed ? 'expand' : 'collapse'" />
          </el-button>
          <el-button text class="mobile-navigation-toggle" aria-label="打开工作台导航" :aria-expanded="mobileNavigationOpen" @click="mobileNavigationOpen = true">
            <WorkspaceIcon name="menu" />
          </el-button>
          <el-breadcrumb class="workspace-breadcrumb" separator="/">
            <el-breadcrumb-item :to="workspaceHome">{{ title }}</el-breadcrumb-item>
            <el-breadcrumb-item v-if="activeItem && activeItem.label !== pageTitle" :to="activeItem.path">{{ activeItem.label }}</el-breadcrumb-item>
            <el-breadcrumb-item>{{ pageTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-actions">
          <WorkspaceSwitcher :current-workspace="workspace" :workspaces="workspaces" @switch="switchWorkspace" />
          <div class="current-user" :title="authStore.displayName">
            <el-avatar :size="28" aria-hidden="true">{{ userInitial }}</el-avatar>
            <span>{{ authStore.displayName }}</span>
          </div>
          <el-button text :loading="loggingOut" :disabled="loggingOut" @click="handleLogout">
            <WorkspaceIcon name="logout" /><span class="logout-label">退出登录</span>
          </el-button>
        </div>
      </header>

      <main class="workspace-main">
        <router-view />
      </main>
    </div>

    <el-drawer v-model="mobileNavigationOpen" title="工作台导航" direction="ltr" size="220px" class="workspace-navigation-drawer">
      <p class="mobile-workspace-title">{{ title }}</p>
      <WorkspaceNavigation :items="menuItems" :active="activeItem?.path" @navigate="mobileNavigationOpen = false" />
    </el-drawer>
  </div>
</template>

<style scoped>
.workspace-layout { --workspace-sidebar-width: 200px; --workspace-panel-top: 78px; min-height: 100vh; background: #f3f5f8; }
.workspace-layout.is-collapsed { --workspace-sidebar-width: 64px; }
.workspace-aside { position: fixed; inset: 0 auto 0 0; z-index: 30; display: flex; flex-direction: column; width: var(--workspace-sidebar-width); overflow-x: hidden; overflow-y: auto; background: #1a1f2e; transition: width .18s ease; }
.workspace-brand { display: flex; align-items: center; justify-content: center; gap: 10px; height: 56px; flex-shrink: 0; color: #fff; text-decoration: none; white-space: nowrap; }
.workspace-brand img { width: 30px; height: 30px; }
.workspace-brand strong { font-size: 15px; font-weight: 600; }
.workspace-category { margin: 18px 24px 10px; color: #8592a8; font-size: 12px; white-space: nowrap; }
.sidebar-footer { margin: auto 20px 20px; padding-top: 32px; color: #8592a8; font-size: 11px; white-space: nowrap; }
.workspace-body { min-width: 0; margin-left: var(--workspace-sidebar-width); transition: margin-left .18s ease; }
.workspace-header { position: sticky; top: 0; z-index: 20; display: flex; align-items: center; justify-content: space-between; gap: 16px; min-height: 56px; padding: 8px 20px 8px 12px; background: #fff; border-bottom: 1px solid #e8ecf2; }
.header-navigation, .header-actions { display: flex; align-items: center; gap: 14px; min-width: 0; }
.header-navigation { flex: 1; }
.header-actions { flex-shrink: 0; gap: 18px; }
.header-navigation > .el-button { margin: 0; padding: 8px; flex-shrink: 0; }
.workspace-breadcrumb { line-height: 1.6; }
.workspace-breadcrumb :deep(.el-breadcrumb__inner) { font-size: 13px; font-weight: 400; }
.current-user { display: flex; align-items: center; gap: 8px; color: #475569; font-size: 13px; }
.current-user .el-avatar { background: #edf4ff; color: #337ecc; font-size: 12px; }
.current-user > span:last-child { max-width: 120px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.logout-label { margin-left: 6px; }
.header-actions > .el-button { padding-inline: 4px; }
.workspace-main { min-width: 0; padding: 22px 24px 32px; }
.mobile-navigation-toggle { display: none; }
.mobile-workspace-title { margin: 8px 24px 18px; color: #8592a8; font-size: 13px; }
@media (max-width: 1050px) {
  .workspace-layout { --workspace-panel-top: 108px; }
  .workspace-header { flex-wrap: wrap; gap: 6px 16px; }
  .header-actions { gap: 12px; margin-left: auto; }
}
@media (max-width: 760px) {
  .workspace-aside { display: none; }
  .workspace-body { margin-left: 0; }
  .desktop-navigation-toggle { display: none; }
  .mobile-navigation-toggle { display: inline-flex; }
  .workspace-header { padding: 8px 12px; gap: 8px; }
  .header-navigation { flex-basis: 100%; }
  .workspace-breadcrumb { overflow: hidden; }
  .header-actions { width: 100%; justify-content: space-between; gap: 8px; padding-left: 4px; }
  .current-user { margin-left: auto; gap: 5px; }
  .current-user > span:last-child { max-width: 75px; }
  .header-actions > .el-button { font-size: 12px; }
  .workspace-main { padding: 18px 14px 28px; }
}
@media (prefers-reduced-motion: reduce) {
  .workspace-aside, .workspace-body { transition: none; }
}
@media (max-width: 380px) {
  .current-user > span:last-child { display: none; }
  .header-actions { gap: 6px; }
}
</style>
