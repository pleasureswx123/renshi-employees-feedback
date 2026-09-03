<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import WorkspaceSwitcher from '@/components/WorkspaceSwitcher.vue'
import { useAuthStore } from '@/stores/auth'
import { usePermissionStore } from '@/stores/permission'

const props = defineProps({
  workspace: { type: String, required: true },
  title: { type: String, required: true }
})

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const permissionStore = usePermissionStore()
const loggingOut = ref(false)

const workspaces = computed(() => permissionStore.availableWorkspaces())
const activeMenu = computed(() => {
  if (route.meta.activeMenu === '/hr/projects' && !permissionStore.hasPermission('feedback:project:list')) {
    return '/hr/progress'
  }
  return route.meta.activeMenu || route.path
})
const menuItems = computed(() => {
  if (props.workspace === 'hr') {
    if (permissionStore.hasPermission('feedback:project:list')) {
      return [{ path: '/hr/projects', label: '评价项目' }]
    }
    if (permissionStore.hasPermission('feedback:progress:view')) {
      return [{ path: '/hr/progress', label: '回收进度' }]
    }
    return []
  }
  return [
    permissionStore.hasPermission('feedback:task:view')
      ? { path: '/employee/todos', label: '我的待办' }
      : null,
    permissionStore.hasPermission('feedback:history:view')
      ? { path: '/employee/reviews', label: '我评价的' }
      : null
  ].filter(Boolean)
})

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
  <el-container class="workspace-layout">
    <el-header class="workspace-header">
      <div>
        <p class="brand-kicker">员工反馈与 360° 评价平台</p>
        <strong class="brand-title">{{ title }}</strong>
      </div>
      <div class="header-actions">
        <WorkspaceSwitcher
          :current-workspace="workspace"
          :workspaces="workspaces"
          @switch="switchWorkspace"
        />
        <span class="current-user">{{ authStore.displayName }}</span>
        <el-button :loading="loggingOut" @click="handleLogout">退出登录</el-button>
      </div>
    </el-header>
    <nav class="mobile-workspace-nav" aria-label="工作台导航">
      <el-menu :default-active="activeMenu" mode="horizontal" :ellipsis="false" router>
        <el-menu-item v-for="item in menuItems" :key="item.path" :index="item.path">{{ item.label }}</el-menu-item>
      </el-menu>
    </nav>
    <el-container>
      <el-aside width="220px" class="workspace-aside">
        <el-menu :default-active="activeMenu" router>
          <el-menu-item v-for="item in menuItems" :key="item.path" :index="item.path">
            {{ item.label }}
          </el-menu-item>
        </el-menu>
      </el-aside>
      <el-main class="workspace-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.workspace-layout {
  min-height: 100vh;
}

.workspace-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 72px;
  border-bottom: 1px solid #e5e7eb;
  background: #fff;
}

.brand-kicker {
  margin: 0 0 3px;
  color: #64748b;
  font-size: 12px;
}

.brand-title {
  color: #111827;
  font-size: 20px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.current-user {
  color: #475569;
}

.workspace-aside {
  border-right: 1px solid #e5e7eb;
  background: #fff;
}

.workspace-aside :deep(.el-menu) {
  border-right: 0;
}

.workspace-main {
  padding: 24px;
  min-width: 0;
}

.mobile-workspace-nav { display: none; }

@media (max-width: 760px) {
  .mobile-workspace-nav { display: block; }
  .workspace-header {
    height: auto;
    padding: 14px 16px;
  }

  .workspace-header,
  .header-actions {
    align-items: flex-start;
    flex-direction: column;
  }

  .workspace-aside {
    display: none;
  }

  .workspace-main {
    padding: 16px;
  }
}
</style>
