<script setup>
import { nextTick, ref } from 'vue'

import { createStableCode } from '@/utils/questionnaireDraft'

const props = defineProps({
  question: { type: Object, required: true },
  canMoveUp: { type: Boolean, default: false },
  canMoveDown: { type: Boolean, default: false }
})

const emit = defineEmits(['change', 'delete', 'duplicate', 'move-up', 'move-down'])
const formRef = ref()
const batchVisible = ref(false)
const batchText = ref('')
const rules = {
  title: [{ required: true, message: '请填写题目标题', trigger: 'blur' }]
}

function changeQuestion(patch) {
  emit('change', { ...props.question, ...patch })
}

function changeOption(index, patch) {
  const options = props.question.options.map((option, optionIndex) =>
    optionIndex === index ? { ...option, ...patch } : option
  )
  changeQuestion({ options })
}

function addOption() {
  changeQuestion({
    options: [
      ...props.question.options,
      {
        optionId: null,
        optionCode: createStableCode('O'),
        optionLabel: `选项${props.question.options.length + 1}`,
        score: 0,
        requiresReason: false,
        sortOrder: props.question.options.length + 1
      }
    ]
  })
}

function removeOption(index) {
  if (props.question.options.length <= 2) return
  changeQuestion({ options: props.question.options.filter((_, optionIndex) => optionIndex !== index) })
}

function openBatchDialog() {
  batchText.value = ''
  batchVisible.value = true
}

function applyBatchOptions() {
  const options = batchText.value
    .split(/\r?\n/)
    .map(line => line.trim())
    .filter(Boolean)
    .map((line, index) => {
      const [label, rawScore] = line.split('|').map(item => item.trim())
      const parsedScore = Number(rawScore)
      return {
        optionId: null,
        optionCode: createStableCode('O'),
        optionLabel: label,
        score: Number.isFinite(parsedScore) && parsedScore >= 0 ? parsedScore : 0,
        requiresReason: false,
        sortOrder: index + 1
      }
    })
  if (options.length < 2) return
  changeQuestion({ options })
  batchVisible.value = false
}

async function validate() {
  await nextTick()
  return formRef.value?.validate()
}

defineExpose({ validate })
</script>

<template>
  <div class="properties-panel">
    <div class="panel-heading">
      <div>
        <p>题目属性</p>
        <strong>单选题</strong>
      </div>
      <div class="question-actions">
        <el-button plain @click="emit('duplicate')">复制题目</el-button>
        <el-button :disabled="!canMoveUp" @click="emit('move-up')">上移</el-button>
        <el-button :disabled="!canMoveDown" @click="emit('move-down')">下移</el-button>
        <el-button type="danger" plain @click="emit('delete')">删除题目</el-button>
      </div>
    </div>

    <el-form ref="formRef" :model="question" :rules="rules" label-position="top">
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
          <el-switch
            :model-value="question.isRequired"
            @change="changeQuestion({ isRequired: $event })"
          />
        </el-form-item>
        <el-form-item label="参与计分">
          <el-switch
            :model-value="question.isScored"
            @change="changeQuestion({ isScored: $event })"
          />
        </el-form-item>
      </div>

      <div class="option-heading">
        <strong>选项与分值</strong>
        <el-button link type="primary" @click="openBatchDialog">批量增加</el-button>
      </div>
      <div v-for="(option, index) in question.options" :key="option.optionCode" class="option-editor">
        <el-form-item
          :label="`选项 ${index + 1}`"
          :prop="`options.${index}.optionLabel`"
          :rules="[{ required: true, message: '选项文本不能为空', trigger: 'blur' }]"
        >
          <el-input
            :model-value="option.optionLabel"
            maxlength="500"
            @input="changeOption(index, { optionLabel: $event })"
          />
        </el-form-item>
        <div class="option-controls">
          <el-form-item label="分值">
            <el-input-number
              :model-value="Number(option.score)"
              :min="0"
              :precision="4"
              controls-position="right"
              @change="changeOption(index, { score: $event ?? 0 })"
            />
          </el-form-item>
          <el-form-item label="要求说明">
            <el-switch
              :model-value="option.requiresReason"
              @change="changeOption(index, { requiresReason: $event })"
            />
          </el-form-item>
          <el-button
            type="danger"
            link
            :disabled="question.options.length <= 2"
            @click="removeOption(index)"
          >
            删除
          </el-button>
        </div>
      </div>
      <el-button class="add-option" plain @click="addOption">增加选项</el-button>
    </el-form>

    <el-dialog v-model="batchVisible" title="批量增加选项" width="520px" append-to-body>
      <el-form label-position="top">
        <el-form-item label="每行一个选项，可用“选项文字 | 分值”格式">
          <el-input
            v-model="batchText"
            type="textarea"
            :rows="8"
            placeholder="非常符合 | 5&#10;比较符合 | 4&#10;一般 | 3"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="batchVisible = false">取消</el-button>
        <el-button type="primary" :disabled="batchText.trim().split(/\r?\n/).filter(Boolean).length < 2" @click="applyBatchOptions">
          应用选项
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.properties-panel {
  display: grid;
  gap: 18px;
}

.panel-heading,
.question-actions,
.option-heading,
.option-controls,
.switch-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.panel-heading {
  align-items: flex-start;
}

.question-actions {
  flex-wrap: wrap;
  justify-content: flex-end;
}

.panel-heading p {
  margin: 0 0 3px;
  color: #909399;
  font-size: 12px;
}

.option-heading {
  margin-bottom: 12px;
}

.option-editor {
  margin-bottom: 14px;
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fafafa;
}

.option-controls {
  align-items: flex-end;
}

.option-controls :deep(.el-form-item),
.switch-row :deep(.el-form-item) {
  margin-bottom: 0;
}

.option-controls :deep(.el-input-number) {
  width: 130px;
}

.add-option {
  width: 100%;
}
</style>
