import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useWorkspaceUiStore = defineStore('workspaceUi', () => {
  // 仅保存本次访问的界面偏好，不缓存账号或业务数据。
  const collapsed = ref(false)
  const compact = ref(false)
  function toggleSidebar() { collapsed.value = !collapsed.value }
  return { collapsed, compact, toggleSidebar }
})
