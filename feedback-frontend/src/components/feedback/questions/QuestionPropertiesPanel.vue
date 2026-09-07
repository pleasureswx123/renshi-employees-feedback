<script setup>
import { computed } from 'vue'

import { getQuestionTypeDefinition } from './questionTypeRegistry'

const props = defineProps({
  question: { type: Object, required: true },
  questionNumber: { type: Number, default: 0 },
  pages: { type: Array, required: true },
  currentPageCode: { type: String, required: true },
  disabled: { type: Boolean, default: false }
})
const emit = defineEmits(['change', 'move-to-page'])
const definition = computed(() => getQuestionTypeDefinition(props.question.questionType))

function changeQuestion(patch) {
  if (!props.disabled) emit('change', { ...props.question, ...patch })
}
</script>

<template>
  <div class="properties-panel">
    <p v-if="questionNumber" class="property-context">正在编辑 · 第 {{ questionNumber }} 题</p>
    <div class="panel-heading">
      <el-tag size="small" effect="plain">{{ definition?.label }}</el-tag>
      <strong :title="question.title">{{ question.title.trim() || '待填写题目内容' }}</strong>
    </div>

    <el-form :model="question" :disabled="disabled" label-position="top" size="small">
      <div class="switch-row">
        <el-form-item label="必答" label-position="left">
          <el-switch :model-value="question.isRequired" @change="changeQuestion({ isRequired: $event })" />
        </el-form-item>
        <el-form-item label="参与计分" label-position="left">
          <el-switch
            :model-value="question.isScored"
            :disabled="question.questionType === 'TEXT'"
            @change="changeQuestion({ isScored: $event })"
          />
        </el-form-item>
      </div>
      <el-form-item label="所在页面">
        <el-select
          :model-value="currentPageCode"
          aria-label="题目所在页面"
          @change="$event !== currentPageCode && emit('move-to-page', $event)"
        >
          <el-option
            v-for="page in pages"
            :key="page.pageCode"
            :label="page.pageTitle"
            :value="page.pageCode"
          />
        </el-select>
      </el-form-item>
    </el-form>

  </div>
</template>

<style scoped>
.properties-panel { display: grid; gap: 14px; }
.property-context { margin: 0; font-size: 13px; font-weight: 600; color: var(--el-color-primary); }
.panel-heading { display: flex; align-items: flex-start; gap: 8px; padding-bottom: 12px; border-bottom: 1px solid var(--fb-border, #ebeef5); }
.switch-row { display: grid; gap: 2px; padding: 4px 10px; margin-bottom: 14px; background: var(--fb-surface-muted, #f6f8fa); border-radius: 6px; }
.panel-heading strong { min-width: 0; overflow-wrap: anywhere; font-size: 14px; line-height: 1.6; }
.panel-heading:deep(.el-tag) { flex: none; }
.properties-panel:deep(.el-form-item) { margin-bottom: 14px; }
.properties-panel:deep(.el-form-item:last-child) { margin-bottom: 0; }
.switch-row:deep(.el-form-item) { align-items: center; margin-bottom: 0; }
.switch-row:deep(.el-form-item__label) { height: auto; margin: 0; padding: 0; line-height: 32px; }
.switch-row:deep(.el-form-item__content) { justify-content: flex-end; }
:deep(.el-select) { width: 100%; }
</style>
