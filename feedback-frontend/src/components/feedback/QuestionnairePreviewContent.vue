<script setup>
import { computed, nextTick, reactive, ref, watch } from 'vue'

import RichTextEditor from './RichTextEditor.vue'
import QuestionRenderer from './questions/QuestionRenderer.vue'
import { getQuestionTypeDefinition } from './questions/questionTypeRegistry'

const props = defineProps({
  draft: { type: Object, required: true },
  pageCode: { type: String, default: '' },
  selectedQuestionCode: { type: String, default: '' },
  compact: { type: Boolean, default: false },
  active: { type: Boolean, default: true }
})
const pages = computed(() => props.pageCode ? props.draft.pages.filter(page => page.pageCode === props.pageCode) : props.draft.pages)
const questions = computed(() => props.draft.pages.flatMap(page => page.questions))
const answers = reactive({})
const questionElements = new Map()
const previewDocumentRef = ref()
const hasDescription = computed(() => hasRichText(props.draft.descriptionDoc))

function hasRichText(node) {
  return Boolean(node?.text?.trim() || node?.content?.some(hasRichText))
}

function resetAnswers() {
  for (const key of Object.keys(answers)) delete answers[key]
}

// 只在答题约束变化时清理该题试填值；修改文案、切换选中题目不会清空其他答案。
const answerSignatures = computed(() => new Map(questions.value.map(question => [question.questionCode, JSON.stringify({
  type: question.questionType, min: question.minScore, max: question.maxScore,
  decimals: question.decimalPlaces, config: question.config,
  options: question.options.map(option => [option.optionCode, option.requiresReason])
})])))
watch(answerSignatures, (current, previous) => {
  for (const code of Object.keys(answers)) if (!current.has(code) || current.get(code) !== previous?.get(code)) delete answers[code]
})

async function revealSelectedQuestion([, pageCode, active], [, previousPageCode, previouslyActive]) {
  if (!props.compact || !props.active) return
  await nextTick()
  const scroller = previewDocumentRef.value?.closest('.el-tabs__content')
  if (!scroller) return
  if (pageCode !== previousPageCode || (active && !previouslyActive)) {
    // 切页时先展示完整问卷标题与说明，空白页也回到开头。
    scroller.scrollTop = 0
    return
  }
  const element = questionElements.get(props.selectedQuestionCode)
  if (!element) return
  const itemRect = element.getBoundingClientRect()
  const scrollRect = scroller.getBoundingClientRect()
  if (itemRect.top < scrollRect.top || itemRect.bottom > scrollRect.bottom) {
    // 仅滚动预览面板，保留画布的编辑位置与输入焦点。
    scroller.scrollTop += itemRect.top - scrollRect.top - 12
  }
}

watch(() => [props.selectedQuestionCode, props.pageCode, props.active], revealSelectedQuestion)
defineExpose({ resetAnswers })
</script>

<template>
  <article ref="previewDocumentRef" :class="['preview-document', { compact }]">
    <header class="preview-document-heading">
      <h2>{{ draft.title || '待填写问卷标题' }}</h2>
      <RichTextEditor v-if="hasDescription" :model-value="draft.descriptionDoc" readonly />
      <p v-else-if="!draft.descriptionDoc && draft.description" class="plain-description">{{ draft.description }}</p>
    </header>
    <section v-for="page in pages" :key="page.pageCode" class="preview-page">
      <el-empty v-if="!page.questions.length" description="添加题目后，即可在这里试填" :image-size="64" />
      <div
        v-for="(question, index) in page.questions"
        :key="question.questionCode"
        :ref="element => element ? questionElements.set(question.questionCode, element) : questionElements.delete(question.questionCode)"
        :class="['preview-question', { 'is-selected': compact && question.questionCode === selectedQuestionCode }]"
        :data-question-code="question.questionCode"
      >
        <header class="preview-question-heading">
          <h3 class="preview-question-title">
            <span class="preview-question-number">{{ index + 1 }}、</span><strong>{{ question.title.trim() || `${getQuestionTypeDefinition(question.questionType)?.label} · 待填写题目内容` }}</strong><span v-if="question.isRequired" class="required-mark" aria-label="必答">*</span>
          </h3>
          <span v-if="compact && question.questionCode === selectedQuestionCode" class="editing-indicator">正在编辑</span>
        </header>
        <p v-if="question.description" class="preview-question-description">{{ question.description }}</p>
        <QuestionRenderer
          :key="answerSignatures.get(question.questionCode)"
          :question="question"
          mode="preview"
          :show-heading="false"
          :model-value="answers[question.questionCode]"
          @update:model-value="answers[question.questionCode] = $event"
        />
      </div>
    </section>
  </article>
</template>

<style scoped>
.preview-document { container-type: inline-size; width: min(760px, 100%); margin: 0 auto; padding: 28px; border-radius: 10px; background: #fff; box-sizing: border-box; }
.preview-document-heading h2 { margin: 0 0 18px; color: #1f2937; font-size: 22px; line-height: 1.5; text-align: center; overflow-wrap: anywhere; }
.plain-description { white-space: pre-wrap; overflow-wrap: anywhere; }
.preview-page { margin-top: 20px; }
.preview-question { margin-top: 24px; overflow-wrap: anywhere; }
.preview-question-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; margin-bottom: 8px; }
.preview-question-title { min-width: 0; margin: 0; color: #111827; font-size: 14px; font-weight: 600; line-height: 1.6; white-space: pre-wrap; }
.required-mark { margin-left: 4px; color: #f56c6c; }
.editing-indicator { flex-shrink: 0; color: #409eff; font-size: 12px; }
.preview-question-description { margin: 0 0 12px; color: #64748b; line-height: 1.6; white-space: pre-wrap; }
.compact { min-height: 640px; padding: 28px clamp(18px, 5%, 36px) 40px; border: 1px solid #c8ced4; border-radius: 0; box-shadow: 0 2px 8px rgb(15 23 42 / 12%); }
.compact .preview-document-heading h2 { font-size: 18px; }
.compact .preview-question { margin-top: 20px; }
.compact .preview-question.is-selected .preview-question-number { color: #409eff; }
.preview-question :deep(.el-input-number) { max-width: 100%; }
.preview-question :deep(.el-slider) { flex-wrap: nowrap; gap: 16px; }
.preview-question :deep(.el-slider__runway.show-input) { min-width: 0; margin-right: 0; }
</style>
