<script setup>
import { decimalToNumber } from '@/utils/fixedDecimal'

const props = defineProps({
  question: { type: Object, required: true },
  mode: { type: String, default: 'preview' },
  showHeading: { type: Boolean, default: true },
  modelValue: { type: Object, default: () => ({ value: null }) }
})

const emit = defineEmits(['update:modelValue'])

function changeValue(value) {
  emit('update:modelValue', { value })
}
</script>

<template>
  <section class="question-block">
    <div v-if="showHeading" class="question-heading">
      <span v-if="question.isRequired" class="required-mark" aria-label="必答">*</span>
      <strong>{{ question.title }}</strong>
    </div>
    <p v-if="showHeading && question.description" class="question-description">{{ question.description }}</p>
    <el-input-number
      :model-value="modelValue?.value ?? (mode === 'preview' ? question.config?.defaultValue : null)"
      :min="decimalToNumber(question.minScore)"
      :max="decimalToNumber(question.maxScore)"
      :precision="question.decimalPlaces"
      controls-position="right"
      :disabled="mode === 'editor' || mode === 'readonly'"
      aria-label="数字评分"
      @change="changeValue"
    />
    <small class="range-hint">允许范围：{{ decimalToNumber(question.minScore).toFixed(question.decimalPlaces) }} 至 {{ decimalToNumber(question.maxScore).toFixed(question.decimalPlaces) }}</small>
    <small v-if="mode === 'answer' && question.config?.defaultValue != null && modelValue?.value == null" class="range-hint">
      参考默认值：{{ question.config.defaultValue }}；请输入分值后才会记录答案
    </small>
  </section>
</template>

<style scoped>
.question-block { display: grid; gap: 12px; }
.question-heading { color: #111827; line-height: 1.6; }
.required-mark { margin-right: 4px; color: #f56c6c; }
.question-description { margin: 0; color: #64748b; line-height: 1.6; }
.range-hint { color: #909399; }
</style>
