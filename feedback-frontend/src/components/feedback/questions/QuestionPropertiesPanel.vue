<script setup>
import { computed, nextTick, ref } from 'vue'

import { getQuestionTypeDefinition } from './questionTypeRegistry'

const props = defineProps({
  question: { type: Object, required: true },
  pages: { type: Array, required: true },
  currentPageCode: { type: String, required: true },
  canMoveUp: { type: Boolean, default: false },
  canMoveDown: { type: Boolean, default: false }
})
const emit = defineEmits(['change', 'delete', 'duplicate', 'move-up', 'move-down', 'move-to-page'])
const commonFormRef = ref()
const specificRef = ref()
const definition = computed(() => getQuestionTypeDefinition(props.question.questionType))
const rules = { title: [{ required: true, message: '请填写题目标题', trigger: 'blur' }] }

function changeQuestion(patch) {
  emit('change', { ...props.question, ...patch })
}

async function validate() {
  await nextTick()
  await commonFormRef.value?.validate()
  return specificRef.value?.validate?.()
}

defineExpose({ validate })
</script>

<template>
  <div class="properties-panel">
    <div class="panel-heading">
      <div><p>题目属性</p><strong>{{ definition?.label }}</strong></div>
      <div class="question-actions">
        <el-button plain @click="emit('duplicate')">复制</el-button>
        <el-button :disabled="!canMoveUp" @click="emit('move-up')">上移</el-button>
        <el-button :disabled="!canMoveDown" @click="emit('move-down')">下移</el-button>
        <el-button type="danger" plain @click="emit('delete')">删除</el-button>
      </div>
    </div>

    <el-form ref="commonFormRef" :model="question" :rules="rules" label-position="top">
      <el-form-item label="题目标题" prop="title">
        <el-input
          :model-value="question.title"
          maxlength="2000"
          show-word-limit
          type="textarea"
          :rows="3"
          @input="changeQuestion({ title: $event })"
        />
      </el-form-item>
      <el-form-item label="题目说明">
        <el-input
          :model-value="question.description"
          maxlength="5000"
          type="textarea"
          :rows="2"
          placeholder="可选，补充答题口径"
          @input="changeQuestion({ description: $event })"
        />
      </el-form-item>
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

    <el-divider />
    <component
      :is="definition?.propertyEditor"
      v-if="definition?.propertyEditor"
      ref="specificRef"
      :question="question"
      @change="emit('change', $event)"
    />
  </div>
</template>

<style scoped>
.properties-panel { display: grid; gap: 16px; }
.panel-heading, .question-actions, .switch-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.panel-heading { align-items: flex-start; }
.panel-heading p { margin: 0 0 3px; color: #909399; font-size: 12px; }
.question-actions { flex-wrap: wrap; justify-content: flex-end; }
.switch-row :deep(.el-form-item) { margin-bottom: 16px; }
:deep(.el-select) { width: 100%; }
</style>
