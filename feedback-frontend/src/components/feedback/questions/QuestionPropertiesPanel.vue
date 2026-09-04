<script setup>
import { computed } from 'vue'

import { getQuestionTypeDefinition } from './questionTypeRegistry'

const props = defineProps({
  question: { type: Object, required: true },
  pages: { type: Array, required: true },
  currentPageCode: { type: String, required: true },
  indicators: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false }
})
const emit = defineEmits(['change', 'move-to-page', 'set-indicator'])
const definition = computed(() => getQuestionTypeDefinition(props.question.questionType))
const indicatorCode = computed(() => props.indicators.find(item => item.questionCodes.includes(props.question.questionCode))?.indicatorCode || '')

function changeQuestion(patch) {
  if (!props.disabled) emit('change', { ...props.question, ...patch })
}
</script>

<template>
  <div class="properties-panel">
    <div class="panel-heading">
      <el-tag size="small" effect="plain">{{ definition?.label }}</el-tag>
      <strong :title="question.title">{{ question.title.trim() || '待填写题目内容' }}</strong>
    </div>

    <el-form :model="question" :disabled="disabled" label-position="top">
      <div class="switch-row">
        <el-form-item label="必答">
          <el-switch :model-value="question.isRequired" @change="changeQuestion({ isRequired: $event })" />
        </el-form-item>
        <el-form-item label="参与计分">
          <el-switch
            :model-value="question.isScored"
            :disabled="question.questionType === 'TEXT'"
            @change="changeQuestion({ isScored: $event })"
          />
        </el-form-item>
      </div>
      <el-form-item v-if="question.isScored && question.questionType !== 'TEXT'" label="评价指标">
        <el-select
          :model-value="indicatorCode"
          clearable
          placeholder="选择所属指标"
          aria-label="题目评价指标"
          @change="emit('set-indicator', question.questionCode, $event || '')"
        >
          <el-option v-for="indicator in indicators" :key="indicator.indicatorCode" :label="indicator.indicatorName" :value="indicator.indicatorCode" />
        </el-select>
        <small v-if="!indicators.length" class="field-hint">先在“评价指标”中添加指标。</small>
      </el-form-item>
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

    <p class="editing-hint">在画布中直接修改题目内容和题型参数。</p>
  </div>
</template>

<style scoped>
.properties-panel { display: grid; gap: 16px; }
.panel-heading, .switch-row { display: flex; align-items: center; gap: 10px; }
.switch-row { justify-content: space-between; }
.panel-heading strong { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 14px; }
.panel-heading :deep(.el-tag) { flex: none; }
.editing-hint { margin: 0; color: #909399; font-size: 12px; line-height: 1.6; }
.field-hint { color: #909399; line-height: 1.6; margin-top: 5px; }
.switch-row :deep(.el-form-item) { margin-bottom: 16px; }
:deep(.el-select) { width: 100%; }
</style>
