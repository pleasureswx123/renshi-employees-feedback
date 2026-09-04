<script setup>
const props = defineProps({
  question: { type: Object, required: true },
  mode: { type: String, default: 'preview' },
  showHeading: { type: Boolean, default: true },
  modelValue: { type: Object, default: () => ({ text: '' }) }
})

const emit = defineEmits(['update:modelValue'])
</script>

<template>
  <section class="question-block">
    <div v-if="showHeading" class="question-heading">
      <span v-if="question.isRequired" class="required-mark" aria-label="必答">*</span>
      <strong>{{ question.title }}</strong>
    </div>
    <p v-if="showHeading && question.description" class="question-description">{{ question.description }}</p>
    <el-input
      :model-value="modelValue?.text || ''"
      type="textarea"
      :rows="mode === 'editor' ? 2 : 4"
      :maxlength="mode === 'answer' ? undefined : question.config.maxLength"
      :show-word-limit="mode !== 'answer'"
      :disabled="mode === 'editor'"
      :readonly="mode === 'readonly'"
      placeholder="请输入回答"
      aria-label="问答内容"
      @input="emit('update:modelValue', { text: $event })"
    />
    <small v-if="mode === 'answer'">{{ [...(modelValue?.text || '')].length }}/{{ question.config.maxLength }} 字</small>
  </section>
</template>

<style scoped>
.question-block { display: grid; gap: 12px; }
.question-heading { color: var(--fb-text-primary, #111827); line-height: 1.6; }
.required-mark { margin-right: 4px; color: #f56c6c; }
.question-description { margin: 0; color: var(--fb-text-muted, #64748b); line-height: 1.6; }
</style>
