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
.workspace-switcher :deep(.el-button) { min-height: 28px; font-size: 12px; }
.workspace-switcher :deep(.el-button.is-disabled) { color: #337ecc; background: #ecf5ff; border-color: #a0cfff; }
</style>
