<script setup>
import { computed } from 'vue'

const props = defineProps({
  question: { type: Object, required: true },
  mode: { type: String, default: 'preview' },
  modelValue: { type: Object, default: () => ({ optionCode: '', reason: '' }) }
})

const emit = defineEmits(['update:modelValue'])
const selectedOption = computed(() =>
  props.question.options.find(option => option.optionCode === props.modelValue?.optionCode)
)

function changeOption(optionCode) {
  emit('update:modelValue', { optionCode, reason: '' })
}

function changeReason(reason) {
  emit('update:modelValue', { optionCode: props.modelValue?.optionCode || '', reason })
}
</script>

<template>
  <section class="single-choice-question">
    <div class="question-heading">
      <span v-if="question.isRequired" class="required-mark" aria-label="必答">*</span>
      <strong>{{ question.title }}</strong>
    </div>
    <p v-if="question.description" class="question-description">{{ question.description }}</p>
    <el-radio-group
      :model-value="modelValue?.optionCode"
      :disabled="mode === 'editor'"
      class="option-list"
      @change="changeOption"
    >
      <el-radio
        v-for="option in question.options"
        :key="option.optionCode"
        :value="option.optionCode"
        border
      >
        <span>{{ option.optionLabel }}</span>
        <small v-if="mode === 'editor'" class="score-hint">{{ Number(option.score) }}分</small>
      </el-radio>
    </el-radio-group>
    <el-input
      v-if="selectedOption?.requiresReason && mode !== 'editor'"
      :model-value="modelValue?.reason"
      type="textarea"
      :rows="3"
      maxlength="500"
      show-word-limit
      placeholder="请说明选择该选项的原因"
      aria-label="附加原因"
      @input="changeReason"
    />
  </section>
</template>

<style scoped>
.single-choice-question {
  display: grid;
  gap: 12px;
}

.question-heading {
  color: #111827;
  line-height: 1.6;
}

.required-mark {
  margin-right: 4px;
  color: #f56c6c;
}

.question-description {
  margin: 0;
  color: #64748b;
  line-height: 1.6;
}

.option-list {
  display: grid;
  gap: 10px;
}

.option-list :deep(.el-radio) {
  width: 100%;
  height: auto;
  min-height: 42px;
  margin: 0;
  white-space: normal;
}

.score-hint {
  margin-left: 8px;
  color: #909399;
}
</style>
