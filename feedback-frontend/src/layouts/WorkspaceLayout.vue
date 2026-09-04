<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import WorkspaceIcon from '@/components/WorkspaceIcon.vue'
import WorkspaceDisplayControls from '@/components/WorkspaceDisplayControls.vue'
import WorkspaceNavigation from '@/components/WorkspaceNavigation.vue'
import WorkspaceSwitcher from '@/components/WorkspaceSwitcher.vue'
import { brand } from '@/config/brand'
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
const sidebarOverride = ref(null)
const sidebarCollapsed = computed(() => sidebarOverride.value ?? ui.collapsed)
const loggingOut = ref(false)
const mobileNavigationOpen = ref(false)
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

// 页面默认状态仅在进入时应用，手动切换不改变其他页面的侧栏偏好。
watch(() => route.path, () => {
  sidebarOverride.value = route.meta.defaultSidebarCollapsed ?? null
}, { immediate: true })

function toggleSidebar() {
  if (sidebarOverride.value === null) ui.toggleSidebar()
  else sidebarOverride.value = !sidebarOverride.value
}

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
  <div class="workspace-layout" :class="{ 'is-collapsed': sidebarCollapsed, 'is-editor': route.name === 'hr-questionnaire-editor' }">
    <aside class="workspace-aside" aria-label="工作台导航">
      <router-link class="workspace-brand" :to="workspaceHome" :title="brand.title" :aria-label="brand.title">
        <img :src="brand.logo" alt="" />
        <span v-if="!sidebarCollapsed" class="workspace-brand-copy"><strong>{{ brand.name }}</strong><small>{{ brand.edition }}</small></span>
      </router-link>
      <p v-if="!sidebarCollapsed" class="workspace-category">{{ title }}</p>
      <WorkspaceNavigation :items="menuItems" :active="activeItem?.path" :collapsed="sidebarCollapsed" />
      <footer v-if="!sidebarCollapsed" class="sidebar-company" aria-label="公司标识">
        <img :src="brand.companyLogo" :alt="brand.companyName" width="1231" height="267" />
      </footer>
    </aside>

    <div class="workspace-body">
      <header class="workspace-header">
        <div class="header-navigation">
          <el-button text class="desktop-navigation-toggle" :aria-label="sidebarCollapsed ? '展开侧栏' : '收起侧栏'" :aria-expanded="!sidebarCollapsed" @click="toggleSidebar">
            <WorkspaceIcon :name="sidebarCollapsed ? 'expand' : 'collapse'" />
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
          <WorkspaceDisplayControls />
          <el-dropdown trigger="click" placement="bottom-end" :disabled="loggingOut" @command="handleLogout">
            <el-button text class="current-user" :title="authStore.displayName" aria-label="用户菜单" :loading="loggingOut" :disabled="loggingOut">
              <el-avatar :size="28" aria-hidden="true">{{ userInitial }}</el-avatar>
              <span class="current-user-name">{{ authStore.displayName }}</span>
              <svg class="user-menu-arrow" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="m4 6 4 4 4-4" /></svg>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout" :disabled="loggingOut"><WorkspaceIcon name="logout" /><span class="logout-label">退出登录</span></el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
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
.workspace-layout { --workspace-sidebar-width: 200px; --workspace-panel-top: 78px; min-height: 100vh; background: var(--fb-page, #f3f5f8); }
.workspace-layout.is-collapsed { --workspace-sidebar-width: 64px; }
.workspace-aside { position: fixed; inset: 0 auto 0 0; z-index: 30; display: flex; flex-direction: column; width: var(--workspace-sidebar-width); overflow-x: hidden; overflow-y: auto; background: #1a1f2e; transition: width .18s ease; }
.workspace-brand { display: flex; align-items: center; justify-content: center; gap: 10px; height: 56px; flex-shrink: 0; color: #fff; text-decoration: none; white-space: nowrap; }
.workspace-brand img { width: 34px; height: 34px; }
.workspace-brand-copy { display: flex; align-items: baseline; gap: 10px; }
.workspace-brand strong { font-size: 20px; font-weight: 650; letter-spacing: 2px; }
.workspace-brand small { color: #a9b8cd; font-size: 11px; font-weight: 400; }
.workspace-category { margin: 18px 24px 10px; color: #8592a8; font-size: 12px; white-space: nowrap; }
.sidebar-company { flex-shrink: 0; margin: auto 16px 18px; padding: 18px 0 0; border-top: 1px solid #34455e; }
.sidebar-company img { display: block; width: 100%; height: auto; }
.workspace-body { min-width: 0; margin-left: var(--workspace-sidebar-width); transition: margin-left .18s ease; }
.workspace-header { position: sticky; top: 0; z-index: 20; display: flex; align-items: center; justify-content: space-between; gap: 16px; min-height: 56px; padding: 8px 20px 8px 12px; background: #243247; border-bottom: 1px solid #34455e; color: #d6e1ef; }
.header-navigation, .header-actions { display: flex; align-items: center; gap: 14px; min-width: 0; }
.header-navigation { flex: 1; }
.header-actions { flex-shrink: 0; gap: 18px; }
.header-navigation > .el-button { margin: 0; padding: 8px; flex-shrink: 0; }
.header-navigation > .el-button, .current-user { --el-button-text-color: #d6e1ef; --el-button-hover-text-color: #fff; --el-button-active-text-color: #fff; --el-button-disabled-text-color: #a7b6ca; --el-fill-color-light: #34455e; --el-fill-color: #3c506b; }
.header-navigation > .el-button:focus-visible, .current-user:focus-visible { outline: 2px solid #93c5fd; outline-offset: 2px; }
.workspace-breadcrumb { line-height: 1.6; }
.workspace-breadcrumb:deep(.el-breadcrumb__inner) { color: #c5d0e0; font-size: 13px; font-weight: 400; }
.workspace-breadcrumb:deep(.el-breadcrumb__inner.is-link:hover), .workspace-breadcrumb :deep(.el-breadcrumb__inner.is-link:focus-visible) { color: #fff; }
.workspace-breadcrumb:deep(.el-breadcrumb__item:last-child .el-breadcrumb__inner), .workspace-breadcrumb :deep(.el-breadcrumb__item:last-child .el-breadcrumb__inner:hover) { color: #fff; font-weight: 500; }
.workspace-breadcrumb:deep(.el-breadcrumb__separator) { color: #8394ac; }
.current-user { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.current-user .el-avatar { background: #3b526f; color: #e0ecff; border: 1px solid #516b8b; font-size: 12px; }
.logout-label { margin-left: 6px; }
.header-actions > .el-button { padding-inline: 4px; }
.workspace-main { min-width: 0; padding: 22px 24px 32px; }
.workspace-layout.is-editor { height: 100dvh; min-height: 0; overflow: hidden; }
.is-editor .workspace-body { display: flex; flex-direction: column; height: 100%; }
.is-editor .workspace-header { flex-shrink: 0; }
.is-editor .workspace-main { flex: 1; min-height: 0; padding: 14px 20px 20px; overflow: hidden; }
.current-user { height: 36px; padding: 4px 6px; }
.current-user:deep(> span) { display: flex; align-items: center; gap: 8px; }
.current-user-name { max-width: 120px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.user-menu-arrow { width: 14px; height: 14px; flex: none; color: #afbdd1; }
.mobile-navigation-toggle { display: none; }
.mobile-workspace-title { margin: 8px 24px 18px; color: #8592a8; font-size: 13px; }
@media (max-width: 1050px) {
  .workspace-layout { --workspace-panel-top: 108px; }
  .workspace-header { flex-wrap: wrap; gap: 6px 16px; }
  .header-actions { gap: 12px; margin-left: auto; }
}
@media (max-width: 760px) {
  .workspace-layout.is-editor { height: auto; overflow: visible; }
  .is-editor .workspace-body { height: auto; }
  .is-editor .workspace-main { overflow: visible; padding: 14px; }
  .workspace-aside { display: none; }
  .workspace-body { margin-left: 0; }
  .desktop-navigation-toggle { display: none; }
  .mobile-navigation-toggle { display: inline-flex; }
  .workspace-header { padding: 8px 12px; gap: 8px; }
  .header-navigation { flex-basis: 100%; }
  .workspace-breadcrumb { overflow: hidden; }
  .header-actions { width: 100%; justify-content: space-between; gap: 8px; padding-left: 4px; }
  .current-user { margin-left: auto; gap: 5px; }
  .current-user-name { max-width: 75px; }
  .header-actions > .el-button { font-size: 12px; }
  .workspace-main { padding: 18px 14px 28px; }
}
@media (prefers-reduced-motion: reduce) {
  .workspace-aside, .workspace-body { transition: none; }
}
@media (max-width: 380px) {
  .current-user-name { display: none; }
  .header-actions { gap: 6px; }
}
</style>
