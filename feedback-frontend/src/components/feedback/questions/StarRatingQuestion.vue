<script setup>
import { computed } from 'vue'

const props = defineProps({
  question: { type: Object, required: true },
  mode: { type: String, default: 'preview' },
  modelValue: { type: Object, default: () => ({ value: null }) }
})

const emit = defineEmits(['update:modelValue'])
const minimum = computed(() => Number(props.question.minScore))
const starCount = computed(() => Number(props.question.maxScore) - minimum.value + 1)
const selectedStars = computed(() => props.modelValue?.value == null ? 0 : Number(props.modelValue.value) - minimum.value + 1)

function changeValue(value) {
  emit('update:modelValue', { value: value ? value + minimum.value - 1 : null })
}
</script>

<template>
  <section class="question-block">
    <div class="question-heading">
      <span v-if="question.isRequired" class="required-mark" aria-label="必答">*</span>
      <strong>{{ question.title }}</strong>
    </div>
    <p v-if="question.description" class="question-description">{{ question.description }}</p>
    <el-rate
      :model-value="selectedStars"
      :max="starCount"
      :disabled="mode === 'editor' || mode === 'readonly'"
      clearable
      show-score
      :score-template="`${modelValue?.value ?? '未作答'} 分`"
      aria-label="星级评分"
      @change="changeValue"
    />
  </section>
</template>

<style scoped>
.question-block { display: grid; gap: 12px; }
.question-heading { color: #111827; line-height: 1.6; }
.required-mark { margin-right: 4px; color: #f56c6c; }
.question-description { margin: 0; color: #64748b; line-height: 1.6; }
</style>
