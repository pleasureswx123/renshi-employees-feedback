import { defineStore } from 'pinia'
import { computed, onScopeDispose, ref } from 'vue'

import { applyTheme, readTheme, saveTheme, THEME_STORAGE_KEY } from '@/utils/appearance'

export const useWorkspaceUiStore = defineStore('workspaceUi', () => {
  // 折叠仅保留在本次访问；主题是浏览器偏好，不缓存账号或业务数据。
  const collapsed = ref(false)
  const compact = ref(false)
  const theme = ref(readTheme())
  const isDark = computed(() => theme.value === 'dark')
  applyTheme(theme.value)

  function toggleTheme() {
    theme.value = isDark.value ? 'light' : 'dark'
    applyTheme(theme.value)
    saveTheme(theme.value)
  }
  function syncTheme(event) {
    if (event.key !== THEME_STORAGE_KEY && event.key !== null) return
    theme.value = readTheme()
    applyTheme(theme.value)
  }
  window.addEventListener('storage', syncTheme)
  onScopeDispose(() => window.removeEventListener('storage', syncTheme))

  function toggleSidebar() { collapsed.value = !collapsed.value }
  return { collapsed, compact, theme, isDark, toggleSidebar, toggleTheme }
})
