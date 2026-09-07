<script setup>
import ArrowDownIcon from '@iconify-vue/lucide/arrow-down'
import ArrowUpIcon from '@iconify-vue/lucide/arrow-up'
import CopyIcon from '@iconify-vue/lucide/copy'
import TrashIcon from '@iconify-vue/lucide/trash-2'
import { computed, nextTick, ref } from 'vue'

import QuestionRenderer from './QuestionRenderer.vue'
import { getQuestionTypeDefinition } from './questionTypeRegistry'

const props = defineProps({
  question: { type: Object, required: true },
  index: { type: Number, required: true },
  active: { type: Boolean, default: false },
  canMoveUp: { type: Boolean, default: false },
  canMoveDown: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false }
})
const emit = defineEmits(['select', 'change', 'duplicate', 'move', 'delete'])
const cardRef = ref()
const titleRef = ref()
const formRef = ref()
const specificRef = ref()
const definition = computed(() => getQuestionTypeDefinition(props.question.questionType))
const actions = computed(() => [
  { name: 'duplicate', label: '复制题目', icon: CopyIcon },
  { name: 'up', label: '上移题目', icon: ArrowUpIcon, disabled: !props.canMoveUp },
  { name: 'down', label: '下移题目', icon: ArrowDownIcon, disabled: !props.canMoveDown },
  { name: 'delete', label: '删除题目', icon: TrashIcon }
])
const rules = { title: [{ required: true, whitespace: true, message: '请填写题目内容', trigger: 'blur' }] }

function select() {
  if (!props.disabled) emit('select', props.question.questionCode)
}

function changeQuestion(patch) {
  if (!props.disabled) emit('change', { ...props.question, ...patch })
}

function runAction(action) {
  if (props.disabled || action.disabled) return
  if (action.name === 'up' || action.name === 'down') {
    emit('move', props.question.questionCode, action.name === 'up' ? -1 : 1)
  } else {
    emit(action.name, props.question.questionCode)
  }
}

function handleKeydown(event) {
  if (event.isComposing) return
  if (event.key === 'Enter' && event.target.tagName === 'INPUT') {
    // 回车确认当前字段，避免单输入框表单触发浏览器默认提交。
    event.preventDefault()
    event.target.blur()
    return
  }
  if (event.target !== event.currentTarget || !['Enter', ' '].includes(event.key)) return
  event.preventDefault()
  select()
  focusTitle()
}

async function focusTitle() {
  await nextTick()
  cardRef.value?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  titleRef.value?.focus()
}

function focusCard() {
  cardRef.value?.focus({ preventScroll: true })
  cardRef.value?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
}

async function validate() {
  await formRef.value?.validate()
  await specificRef.value?.validate?.()
}

defineExpose({ validate, focusTitle, focusCard })
</script>

<template>
  <article
    ref="cardRef"
    :class="['question-card', { active, 'content-empty': !question.title.trim() }]"
    :aria-label="`第 ${index + 1} 题 · ${definition?.label}`"
    :tabindex="disabled ? -1 : 0"
    @click="select"
    @focusin="select"
    @keydown="handleKeydown"
  >
    <header class="card-heading">
      <div class="question-index">
        <span>第 {{ index + 1 }} 题</span>
        <span class="question-type-badge">
          <component :is="definition?.icon" width="16" height="16" aria-hidden="true" />
          {{ definition?.label }}
        </span>
        <span class="answer-hint">{{ definition?.answerHint }}</span>
        <span v-if="question.isRequired" class="required-hint">必答</span>
        <span v-if="!question.isScored" class="unscored-hint">不计分</span>
      </div>
      <div class="question-actions" role="group" aria-label="题目操作" @click.stop>
        <el-tooltip
          v-for="action in actions"
          :key="action.name"
          :content="action.disabled ? (action.name === 'up' ? '已是本页第一题' : '已是本页最后一题') : action.label"
          :trigger="['hover', 'focus']"
          :trigger-keys="[]"
          :show-after="200"
          :enterable="false"
        >
          <span class="action-target">
            <el-button
              :aria-label="action.label"
              :disabled="disabled || action.disabled"
              :type="action.name === 'delete' ? 'danger' : 'default'"
              text
              class="icon-action"
              @click.stop="runAction(action)"
            >
              <component :is="action.icon" width="17" height="17" aria-hidden="true" />
            </el-button>
          </span>
        </el-tooltip>
      </div>
    </header>

    <el-form ref="formRef" :model="question" :rules="rules" :disabled="disabled" label-position="top" class="content-form">
      <el-form-item label="题目内容" prop="title" class="title-field">
        <el-input
          ref="titleRef"
          :model-value="question.title"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 6 }"
          maxlength="2000"
          :placeholder="definition?.contentPlaceholder || '请输入员工需要回答的问题'"
          @input="changeQuestion({ title: $event })"
        />
      </el-form-item>
      <el-form-item v-show="active || question.description" label="题目说明" class="description-field">
        <el-input
          :model-value="question.description"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 5 }"
          maxlength="5000"
          placeholder="添加题目说明（选填）"
          @input="changeQuestion({ description: $event })"
        />
      </el-form-item>
    </el-form>

    <QuestionRenderer
      v-if="!active || question.questionType !== 'SINGLE_CHOICE'"
      :question="question"
      mode="editor"
      :show-heading="false"
      class="question-preview"
    />
    <component
      :is="definition.propertyEditor"
      v-if="active && definition?.propertyEditor"
      ref="specificRef"
      :question="question"
      :disabled="disabled"
      :class="['question-settings', { 'with-preview': question.questionType !== 'SINGLE_CHOICE' }]"
      @change="!disabled && emit('change', $event)"
    />
  </article>
</template>

<style scoped>
.question-card { container-type: inline-size; margin-top: 14px; min-width: 0; padding: 16px; border: 1px solid var(--fb-border, #e5e7eb); border-radius: 12px; background: var(--fb-surface, #fff); outline: none; scroll-margin-block: 90px; transition: border-color .15s, box-shadow .15s; }
.question-card:hover { border-color: var(--fb-primary-border, #a0cfff); }
.question-card.active, .question-card:focus-visible { border-color: #409eff; box-shadow: 0 0 0 2px rgb(64 158 255 / 12%); }
.card-heading { display: flex; align-items: center; justify-content: space-between; gap: 8px; min-height: 28px; margin-bottom: 4px; }
.question-index { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; color: var(--fb-text-muted, #909399); font-size: 12px; }
.question-type-badge { display: inline-flex; align-items: center; gap: 5px; padding: 1px 6px; border: 1px solid var(--fb-primary-border, #d9ecff); border-radius: 4px; color: var(--fb-primary-text, #337ecc); background: var(--fb-primary-bg, #ecf5ff); font-size: 13px; font-weight: 500; line-height: 20px; }
.answer-hint { color: var(--fb-text-muted, #73767a); }
.required-hint { color: #f56c6c; }
.unscored-hint { color: var(--fb-text-muted, #909399); }
.question-actions { display: flex; flex: none; gap: 2px; visibility: hidden; opacity: 0; pointer-events: none; }
.question-card:hover .question-actions,
.question-card:focus-within .question-actions,
.question-card.active .question-actions { visibility: visible; opacity: 1; pointer-events: auto; }
.action-target { display: inline-flex; }
.icon-action { width: 28px; height: 28px; padding: 0; border-radius: 5px; }
.icon-action:not(.el-button--danger):not(:disabled) { color: var(--fb-text-regular, #606266); }
.icon-action:focus-visible { outline: 2px solid #409eff; outline-offset: 1px; }
.title-field:deep(.el-form-item__label) { height: auto; margin-bottom: 2px; color: var(--fb-text-regular, #606266); font-size: 12px; line-height: 18px; }
/* 将隐藏标签约束在本字段内，避免长问卷把外层页面撑出空白滚动区。 */
.description-field { position: relative; }
.description-field:deep(.el-form-item__label) { position: absolute; width: 1px; height: 1px; margin: -1px; padding: 0; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
.content-form:deep(.el-form-item) { margin-bottom: 6px; }
.content-form:deep(.el-textarea__inner) { padding: 3px 6px; resize: none; background: transparent; box-shadow: 0 0 0 1px transparent inset; }
.content-form:deep(.el-form-item__error), .question-settings :deep(.el-form-item__error) { position: static; width: 100%; line-height: 16px; }
.content-form:deep(.el-textarea__inner:hover) { background: var(--fb-surface-muted, #f8fafc); box-shadow: 0 0 0 1px var(--fb-border-strong, #dcdfe6) inset; }
.content-form:deep(.el-textarea__inner:focus) { background: var(--fb-surface, #fff); box-shadow: 0 0 0 1px #409eff inset; }
.content-form:deep(.is-error .el-textarea__inner) { box-shadow: 0 0 0 1px #f56c6c inset; }
.title-field:deep(.el-textarea__inner) { color: var(--fb-text-primary, #303133); font-size: 16px; font-weight: 600; line-height: 1.5; }
.active .title-field:deep(.el-textarea__inner), .content-empty .title-field :deep(.el-textarea__inner) { box-shadow: 0 0 0 1px var(--fb-border-strong, #dcdfe6) inset; }
.title-field:deep(.el-textarea__inner::placeholder) { color: var(--fb-text-muted, #909399); font-size: 14px; font-weight: 400; }
.title-field:deep(.el-textarea__inner:focus) { box-shadow: 0 0 0 1px #409eff inset; }
.title-field.is-error:deep(.el-textarea__inner) { box-shadow: 0 0 0 1px #f56c6c inset; }
.description-field:deep(.el-textarea__inner) { color: var(--fb-text-regular, #606266); font-size: 13px; line-height: 1.6; }
.question-preview { margin: 4px 6px 0; }
.question-preview:deep(.option-list) { gap: 4px; }
.question-preview:deep(.el-radio) { min-height: 30px; padding: 4px 10px; }
.question-preview.question-block { gap: 6px; }
.with-preview { margin-top: 8px; padding-top: 8px; border-top: 1px dashed var(--fb-border, #e4e7ed); }
.question-settings:deep(.el-form-item) { margin-bottom: 8px; }
.question-settings:deep(.el-form-item__label) { margin-bottom: 3px; line-height: 18px; }
.question-settings:deep(.el-alert) { padding: 6px 10px; }
.question-settings:deep(.option-heading) { margin-bottom: 6px; }
.question-settings:deep(.option-editor) { margin-bottom: 8px; }
.question-settings:deep(.option-editor .el-form-item) { margin-bottom: 0; }
.question-settings.score-settings { grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 0 12px; max-width: 800px; }
.question-settings.score-settings:has(.setting-hint) { grid-template-columns: minmax(120px, 160px) minmax(0, 1fr); max-width: 560px; }
@container (min-width: 520px) {
  .question-settings:not(.score-settings):has(> .el-alert) { display: grid; grid-template-columns: 160px minmax(0, 1fr); align-items: center; gap: 12px; }
}
@media (hover: none) {
  .question-actions { visibility: visible; opacity: 1; pointer-events: auto; }
}
@media (max-width: 600px) {
  .question-card { padding: 10px; }
  .card-heading { align-items: flex-start; flex-wrap: wrap; }
  .question-actions { margin-left: auto; }
}
</style>
