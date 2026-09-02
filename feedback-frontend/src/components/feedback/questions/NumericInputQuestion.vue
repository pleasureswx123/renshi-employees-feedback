<script setup>
import { decimalToNumber } from '@/utils/fixedDecimal'

const props = defineProps({
  question: { type: Object, required: true },
  mode: { type: String, default: 'preview' },
  modelValue: { type: Object, default: () => ({ value: null }) }
})

const emit = defineEmits(['update:modelValue'])

function changeValue(value) {
  emit('update:modelValue', { value })
}
</script>

<template>
  <section class="question-block">
    <div class="question-heading">
      <span v-if="question.isRequired" class="required-mark" aria-label="必答">*</span>
      <strong>{{ question.title }}</strong>
    </div>
    <p v-if="question.description" class="question-description">{{ question.description }}</p>
    <el-input-number
      :model-value="modelValue?.value ?? question.config?.defaultValue ?? null"
      :min="decimalToNumber(question.minScore)"
      :max="decimalToNumber(question.maxScore)"
      :precision="question.decimalPlaces"
      controls-position="right"
      :disabled="mode === 'editor'"
      aria-label="数字评分"
      @change="changeValue"
    />
    <small class="range-hint">允许范围：{{ question.minScore }} 至 {{ question.maxScore }}</small>
  </section>
</template>

<style scoped>
.question-block { display: grid; gap: 12px; }
.question-heading { color: #111827; line-height: 1.6; }
.required-mark { margin-right: 4px; color: #f56c6c; }
.question-description { margin: 0; color: #64748b; line-height: 1.6; }
.range-hint { color: #909399; }
</style>
