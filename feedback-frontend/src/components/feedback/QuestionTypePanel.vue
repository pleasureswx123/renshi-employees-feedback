<script setup>
import { QUESTION_TYPE_DEFINITIONS } from './questions/questionTypeRegistry'

defineEmits(['add'])
</script>

<template>
  <section class="type-panel">
    <div class="panel-title"><strong>题型面板</strong></div>
    <el-button
      v-for="definition in QUESTION_TYPE_DEFINITIONS"
      :key="definition.type"
      class="question-type-button"
      plain
      @click="$emit('add', definition.type)"
    >
      <span><b>{{ definition.label }}</b><small>{{ definition.description }}</small></span>
    </el-button>
  </section>
</template>

<style scoped>
.panel-title { margin-bottom: 12px; }
.question-type-button { width: 100%; height: auto; margin: 0 0 8px; padding: 12px; white-space: normal; }
.question-type-button :deep(span) { display: grid; gap: 3px; justify-items: start; text-align: left; }
.question-type-button small { color: #909399; line-height: 1.4; }
</style>
