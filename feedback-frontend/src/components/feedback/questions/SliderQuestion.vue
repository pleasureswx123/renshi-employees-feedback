<script setup>
import { computed } from 'vue'

import { decimalToNumber } from '@/utils/fixedDecimal'

const props = defineProps({
  question: { type: Object, required: true },
  mode: { type: String, default: 'preview' },
  modelValue: { type: Object, default: () => ({ value: null, touched: false }) }
})

const emit = defineEmits(['update:modelValue'])
const fallbackValue = computed(() =>
  props.question.config?.defaultValue ?? props.question.minScore
)
const displayValue = computed(() => props.modelValue?.value ?? fallbackValue.value)

function changeValue(value) {
  emit('update:modelValue', { value, touched: true })
}
</script>

<template>
  <section class="question-block">
    <div class="question-heading">
      <span v-if="question.isRequired" class="required-mark" aria-label="必答">*</span>
      <strong>{{ question.title }}</strong>
    </div>
    <p v-if="question.description" class="question-description">{{ question.description }}</p>
    <el-slider
      :model-value="decimalToNumber(displayValue)"
      :min="decimalToNumber(question.minScore)"
      :max="decimalToNumber(question.maxScore)"
      :step="decimalToNumber(question.config.step)"
      :disabled="mode === 'editor'"
      show-input
      aria-label="滑动评分"
      @input="changeValue"
    />
    <small v-if="mode !== 'editor' && !modelValue?.touched" class="unanswered-hint">
      尚未作答，移动滑块或使用方向键后才会记录答案
    </small>
  </section>
</template>

<style scoped>
.question-block { display: grid; gap: 12px; }
.question-heading { color: #111827; line-height: 1.6; }
.required-mark { margin-right: 4px; color: #f56c6c; }
.question-description { margin: 0; color: #64748b; line-height: 1.6; }
.unanswered-hint { color: #e6a23c; }
</style>
