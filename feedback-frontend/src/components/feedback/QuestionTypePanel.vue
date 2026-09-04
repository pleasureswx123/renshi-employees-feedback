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
.panel-title { margin-bottom: 12px; }
.type-list { display: grid; gap: 8px; }
.type-list .question-type-button { width: 100%; height: 38px; margin: 0; padding: 0 12px; justify-content: flex-start; border-radius: 5px; }
.question-type-button :deep(> span) { display: flex; align-items: center; gap: 10px; min-width: 0; }
.question-type-icon { flex-shrink: 0; color: #7b8798; }
.question-type-label { font-size: 13px; line-height: 1.4; }
.question-type-button:hover .question-type-icon,
.question-type-button:focus-visible .question-type-icon { color: #409eff; }
.question-type-button:focus-visible { outline: 2px solid #409eff; outline-offset: 2px; }
:global(.question-type-tooltip) { max-width: 260px; line-height: 1.6; }
</style>
