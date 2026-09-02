<script setup>
defineProps({
  currentWorkspace: { type: String, required: true },
  workspaces: { type: Array, required: true }
})

const emit = defineEmits(['switch'])
</script>

<template>
  <div v-if="workspaces.length > 1" class="workspace-switcher" aria-label="工作台切换">
    <el-button
      v-for="workspace in workspaces"
      :key="workspace.key"
      :type="workspace.key === currentWorkspace ? 'primary' : 'default'"
      :disabled="workspace.key === currentWorkspace"
      @click="emit('switch', workspace)"
    >
      {{ workspace.label }}
    </el-button>
  </div>
</template>

<style scoped>
.workspace-switcher {
  display: flex;
  gap: 8px;
}
</style>
