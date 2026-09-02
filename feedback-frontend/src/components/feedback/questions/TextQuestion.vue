<script setup>
const props = defineProps({
  question: { type: Object, required: true },
  mode: { type: String, default: 'preview' },
  modelValue: { type: Object, default: () => ({ text: '' }) }
})

const emit = defineEmits(['update:modelValue'])
</script>

<template>
  <section class="question-block">
    <div class="question-heading">
      <span v-if="question.isRequired" class="required-mark" aria-label="必答">*</span>
      <strong>{{ question.title }}</strong>
    </div>
    <p v-if="question.description" class="question-description">{{ question.description }}</p>
    <el-input
      :model-value="modelValue?.text || ''"
      type="textarea"
      :rows="4"
      :maxlength="question.config.maxLength"
      show-word-limit
      :disabled="mode === 'editor'"
      placeholder="请输入回答"
      aria-label="问答内容"
      @input="emit('update:modelValue', { text: $event })"
    />
  </section>
</template>

<style scoped>
.question-block { display: grid; gap: 12px; }
.question-heading { color: #111827; line-height: 1.6; }
.required-mark { margin-right: 4px; color: #f56c6c; }
.question-description { margin: 0; color: #64748b; line-height: 1.6; }
</style>
