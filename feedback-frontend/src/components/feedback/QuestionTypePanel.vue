<script setup>
import { QUESTION_TYPE_DEFINITIONS } from './questions/questionTypeRegistry'

defineEmits(['add'])
</script>

<template>
  <section class="type-panel">
    <div class="panel-title"><strong>题型面板</strong></div>
    <div class="type-list">
      <el-tooltip
        v-for="definition in QUESTION_TYPE_DEFINITIONS"
        :key="definition.type"
        :content="definition.description"
        placement="right"
        popper-class="question-type-tooltip"
        :show-after="250"
        :enterable="false"
        :trigger="['hover', 'focus']"
        :trigger-keys="[]"
      >
        <el-button
          class="question-type-button"
          :aria-label="`${definition.label} ${definition.description}`"
          plain
          @click="$emit('add', definition.type)"
        >
          <component
            :is="definition.icon"
            class="question-type-icon"
            width="18"
            height="18"
            aria-hidden="true"
          />
          <span class="question-type-label">{{ definition.label }}</span>
        </el-button>
      </el-tooltip>
    </div>
  </section>
</template>

<style scoped>
.type-panel { flex: none; padding: 12px 10px 10px; border: 1px solid var(--el-color-primary-light-7); border-top: 3px solid var(--el-color-primary); border-radius: 8px; background: var(--el-color-primary-light-9); box-shadow: 0 2px 8px rgb(64 158 255 / 8%); }
.panel-title { margin-bottom: 10px; color: var(--fb-primary-text, #244d75); font-size: 14px; }
.type-list { display: grid; gap: 6px; }
.type-list .question-type-button { width: 100%; height: 32px; margin: 0; padding: 0 10px; justify-content: flex-start; border-color: var(--el-color-primary-light-7); border-radius: 5px; color: var(--fb-primary-text, #244d75); background: var(--fb-surface, #fff); }
.type-list .question-type-button:hover, .type-list .question-type-button:focus-visible { border-color: var(--el-color-primary); color: var(--el-color-primary-dark-2); background: var(--el-color-primary-light-8); }
.question-type-button:deep(> span) { display: flex; align-items: center; gap: 10px; min-width: 0; }
.question-type-icon { flex-shrink: 0; color: var(--el-color-primary); }
.question-type-label { font-size: 13px; font-weight: 500; line-height: 1.4; }
.question-type-button:hover .question-type-icon,
.question-type-button:focus-visible .question-type-icon { color: #409eff; }
.question-type-button:focus-visible { outline: 2px solid #409eff; outline-offset: 2px; }
:global(.question-type-tooltip) { max-width: 260px; line-height: 1.6; }
</style>
