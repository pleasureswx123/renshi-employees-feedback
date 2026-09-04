<script setup>
import { computed } from 'vue'

import { getQuestionTypeDefinition } from './questionTypeRegistry'

const props = defineProps({
  question: { type: Object, required: true },
  mode: { type: String, default: 'preview' },
  showHeading: { type: Boolean, default: true },
  modelValue: { type: Object, default: () => ({ optionCode: '', reason: '' }) }
})

const emit = defineEmits(['update:modelValue'])
const definition = computed(() => getQuestionTypeDefinition(props.question.questionType))
const unansweredReadonly = computed(() => {
  if (props.mode !== 'readonly') return false
  if (definition.value?.answerType === 'option') return !props.modelValue?.optionCode
  if (definition.value?.answerType === 'text') return !props.modelValue?.text?.trim()
  return props.modelValue?.value == null
})

function updateAnswer(value) {
  if (!['editor', 'readonly'].includes(props.mode)) emit('update:modelValue', value)
}
</script>

<template>
  <section v-if="unansweredReadonly" class="unanswered-question">
    <strong v-if="showHeading">{{ question.title }}</strong>
    <p v-if="showHeading && question.description">{{ question.description }}</p>
    <p>未作答</p>
  </section>
  <component
    :is="definition.renderer"
    v-else-if="definition"
    :question="question"
    :mode="mode"
    :show-heading="showHeading"
    :model-value="modelValue"
    @update:model-value="updateAnswer"
  />
  <el-alert v-else title="暂不支持该题型" type="warning" :closable="false" />
</template>
