<script setup>
import { computed } from 'vue'

import { getQuestionTypeDefinition } from './questionTypeRegistry'

const props = defineProps({
  question: { type: Object, required: true },
  mode: { type: String, default: 'preview' },
  modelValue: { type: Object, default: () => ({ optionCode: '', reason: '' }) }
})

const emit = defineEmits(['update:modelValue'])
const definition = computed(() => getQuestionTypeDefinition(props.question.questionType))
</script>

<template>
  <component
    :is="definition.renderer"
    v-if="definition"
    :question="question"
    :mode="mode"
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
  />
  <el-alert v-else title="暂不支持该题型" type="warning" :closable="false" />
</template>
