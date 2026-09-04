<script setup>
import { computed } from 'vue'

const props = defineProps({
  question: { type: Object, required: true },
  mode: { type: String, default: 'preview' },
  showHeading: { type: Boolean, default: true },
  modelValue: { type: Object, default: () => ({ optionCode: '', reason: '' }) }
})

const emit = defineEmits(['update:modelValue'])
const selectedOption = computed(() =>
  props.question.options.find(option => option.optionCode === props.modelValue?.optionCode)
)
const reasonLength = computed(() => [...(props.modelValue?.reason || '')].length)

function changeOption(optionCode) {
  emit('update:modelValue', { optionCode, reason: '' })
}

function changeReason(reason) {
  emit('update:modelValue', { optionCode: props.modelValue?.optionCode || '', reason })
}
</script>

<template>
  <section class="single-choice-question" :class="{ 'is-preview': mode === 'preview' }">
    <div v-if="showHeading" class="question-heading">
      <span v-if="question.isRequired" class="required-mark" aria-label="必答">*</span>
      <strong>{{ question.title }}</strong>
    </div>
    <p v-if="showHeading && question.description" class="question-description">{{ question.description }}</p>
    <el-radio-group
      :model-value="modelValue?.optionCode"
      :disabled="mode === 'editor' || mode === 'readonly'"
      class="option-list"
      @change="changeOption"
    >
      <el-radio
        v-for="option in question.options"
        :key="option.optionCode"
        :value="option.optionCode"
        :border="mode !== 'preview'"
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
      :readonly="mode === 'readonly'"
      :maxlength="mode === 'answer' ? undefined : 500"
      :show-word-limit="mode !== 'answer'"
      placeholder="请说明选择该选项的原因"
      aria-label="附加原因"
      @input="changeReason"
    />
    <small v-if="selectedOption?.requiresReason && mode === 'answer'">{{ reasonLength }}/500 字</small>
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

.option-list :deep(.el-radio__label) { white-space: normal; overflow-wrap: anywhere; min-width: 0; }

.is-preview .option-list { gap: 2px; }
.is-preview .option-list :deep(.el-radio) { min-height: 32px; padding: 4px 0; box-sizing: border-box; }
.is-preview .option-list :deep(.el-radio__label) { line-height: 1.6; }

.score-hint {
  margin-left: 8px;
  color: #909399;
}
</style>
