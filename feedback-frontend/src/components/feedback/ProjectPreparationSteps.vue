<script setup>
import { PROJECT_PREPARATION_STEPS } from '@/constants/projectPreparation'

const props = defineProps({
  active: { type: Number, required: true },
  completed: { type: Array, default: () => [] },
  skipped: { type: Array, default: () => [] },
  disabledSteps: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false },
  descriptions: { type: Array, default: () => [] }
})
const emit = defineEmits(['select'])
function status(index) {
  if (index === props.active) return 'process'
  return props.completed.includes(index) || props.skipped.includes(index) ? 'success' : 'wait'
}
function select(index) {
  if (!props.disabled && !props.disabledSteps.includes(index) && !props.skipped.includes(index)) emit('select', index)
}
</script>

<template>
  <nav class="preparation-steps" aria-label="评价准备流程">
    <div class="steps-scroll">
      <el-steps :active="active" finish-status="success" align-center>
        <el-step v-for="(title, index) in PROJECT_PREPARATION_STEPS" :key="title" :status="status(index)">
          <template #title>
            <el-button text size="small" :disabled="disabled || disabledSteps.includes(index) || skipped.includes(index)" :aria-label="`第${index + 1}步：${title}`" :aria-current="active === index ? 'step' : undefined" @click="select(index)">{{ title }}</el-button>
          </template>
          <template #description>
            <span :title="descriptions[index]">{{ skipped.includes(index) ? '无需配置 · 已跳过' : active === index ? '当前步骤' : descriptions[index] }}</span>
          </template>
        </el-step>
      </el-steps>
    </div>
  </nav>
</template>

<style scoped>
.preparation-steps { min-width: 0; padding: 10px 12px 8px; border: 1px solid var(--fb-border, #e5e7eb); border-radius: 8px; background: var(--fb-surface, #fff); }
.steps-scroll { overflow-x: auto; }
.steps-scroll:deep(.el-steps) { min-width: 660px; }
.preparation-steps:deep(.el-step__icon) { width: 22px; height: 22px; font-size: 12px; }
.preparation-steps:deep(.el-step__line) { top: 10px; }
.preparation-steps:deep(.el-step__head.is-process), .preparation-steps:deep(.el-step__title.is-process) { color: var(--el-color-primary); border-color: var(--el-color-primary); }
.preparation-steps:deep(.el-step__title) { line-height: 28px; }
.preparation-steps:deep(.el-step__title .el-button) { height: 26px; padding: 3px 6px; font-size: 13px; font-weight: 600; color: inherit; }
.preparation-steps:deep(.el-step__title .el-button:disabled) { opacity: .65; }
.preparation-steps:deep(.el-step__description) { margin: 0; padding: 0 4px; min-height: 18px; font-size: 11px; line-height: 18px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--fb-text-muted, #73767a); }
</style>
