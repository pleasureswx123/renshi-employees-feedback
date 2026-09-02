import { markRaw } from 'vue'

import SingleChoiceQuestion from './SingleChoiceQuestion.vue'

export const QUESTION_TYPE_REGISTRY = Object.freeze({
  SINGLE_CHOICE: Object.freeze({
    type: 'SINGLE_CHOICE',
    label: '单选题',
    description: '从多个选项中选择一项，可配置分值和附加原因。',
    renderer: markRaw(SingleChoiceQuestion)
  })
})

export function getQuestionTypeDefinition(questionType) {
  return QUESTION_TYPE_REGISTRY[questionType] || null
}
