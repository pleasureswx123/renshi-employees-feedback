<script setup>
defineProps({
  currentWorkspace: { type: String, required: true },
  workspaces: { type: Array, required: true }
})

const emit = defineEmits(['switch'])
</script>

<template>
  <el-button-group v-if="workspaces.length > 1" class="workspace-switcher" aria-label="工作台切换">
    <el-button
      v-for="workspace in workspaces"
      :key="workspace.key"
      :type="workspace.key === currentWorkspace ? 'primary' : 'default'"
      :disabled="workspace.key === currentWorkspace"
      :aria-pressed="workspace.key === currentWorkspace"
      size="small"
      @click="emit('switch', workspace)"
    >
      {{ workspace.label }}
    </el-button>
  </el-button-group>
</template>

<style scoped>
.workspace-switcher {
  display: flex;
  flex-shrink: 0;
}
.workspace-switcher :deep(.el-button) {
  --el-button-text-color: #d6e1ef;
  --el-button-bg-color: transparent;
  --el-button-border-color: #536276;
  --el-button-hover-text-color: #fff;
  --el-button-hover-bg-color: #34455e;
  --el-button-hover-border-color: #7790af;
  --el-button-active-text-color: #fff;
  --el-button-active-bg-color: #3c506b;
  --el-button-active-border-color: #93c5fd;
  min-height: 28px;
  font-size: 12px;
}
.workspace-switcher :deep(.el-button.is-disabled) { color: #fff; background: #2563eb; border-color: #2563eb; }
.workspace-switcher :deep(.el-button:focus-visible) { outline: 2px solid #93c5fd; outline-offset: 2px; }
</style>
