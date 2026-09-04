<script setup>
import WorkspaceIcon from './WorkspaceIcon.vue'

defineProps({
  items: { type: Array, required: true },
  active: { type: String, default: '' },
  collapsed: { type: Boolean, default: false }
})
const emit = defineEmits(['navigate'])
</script>

<template>
  <el-menu class="workspace-menu" :default-active="active" :collapse="collapsed" :collapse-transition="false" router @select="emit('navigate')">
    <el-menu-item v-for="item in items" :key="item.path" :index="item.path">
      <el-icon><WorkspaceIcon :name="item.icon" /></el-icon>
      <template #title><span>{{ item.label }}</span></template>
    </el-menu-item>
  </el-menu>
</template>

<style scoped>
.workspace-menu {
  --el-menu-bg-color: #1a1f2e;
  --el-menu-text-color: #bcc6d6;
  --el-menu-active-color: #66b1ff;
  --el-menu-hover-bg-color: #263445;
  --el-menu-item-height: 48px;
  border-right: 0;
}
.workspace-menu:not(.el-menu--collapse) { width: 200px; }
.workspace-menu :deep(.el-menu-item) { margin: 5px 10px; border-radius: 5px; }
.workspace-menu :deep(.el-menu-item.is-active) { background: #203b58; }
.workspace-menu :deep(.el-icon) { margin-right: 10px; }
.workspace-menu.el-menu--collapse :deep(.el-menu-item) { margin-inline: 0; }
</style>
