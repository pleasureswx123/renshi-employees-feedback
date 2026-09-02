<script setup>
import { nextTick, ref } from 'vue'

import { decimalToNumber, normalizeDecimal } from '@/utils/fixedDecimal'
import { createStableCode } from '@/utils/stableCode'

const props = defineProps({ question: { type: Object, required: true } })
const emit = defineEmits(['change'])
const formRef = ref()
const batchVisible = ref(false)
const batchText = ref('')

function changeQuestion(patch) {
  emit('change', { ...props.question, ...patch })
}

function changeOption(index, patch) {
  changeQuestion({
    options: props.question.options.map((option, optionIndex) =>
      optionIndex === index ? { ...option, ...patch } : option
    )
  })
}

function addOption() {
  changeQuestion({
    options: [
      ...props.question.options,
      {
        optionId: null,
        optionCode: createStableCode('O'),
        optionLabel: `选项${props.question.options.length + 1}`,
        score: '0.0000',
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

function applyBatchOptions() {
  const options = batchText.value
    .split(/\r?\n/)
    .map(line => line.trim())
    .filter(Boolean)
    .map((line, index) => {
      const [label, rawScore] = line.split('|').map(item => item.trim())
      let score = '0.0000'
      try {
        score = normalizeDecimal(rawScore || 0)
      } catch {
        score = '0.0000'
      }
      return {
        optionId: null,
        optionCode: createStableCode('O'),
        optionLabel: label,
        score,
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
  <div>
    <div class="option-heading">
      <strong>选项与分值</strong>
      <el-button link type="primary" @click="batchVisible = true">批量增加</el-button>
    </div>
    <el-form ref="formRef" :model="question" label-position="top">
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
              :model-value="decimalToNumber(option.score)"
              :min="0"
              :precision="4"
              controls-position="right"
              @change="changeOption(index, { score: normalizeDecimal($event ?? 0) })"
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
          >删除</el-button>
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
        <el-button
          type="primary"
          :disabled="batchText.trim().split(/\r?\n/).filter(Boolean).length < 2"
          @click="applyBatchOptions"
        >应用选项</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.option-heading,
.option-controls { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.option-heading { margin-bottom: 12px; }
.option-editor { margin-bottom: 14px; padding: 12px; border: 1px solid #e5e7eb; border-radius: 8px; background: #fafafa; }
.option-controls { align-items: flex-end; }
.option-controls :deep(.el-form-item) { margin-bottom: 0; }
.option-controls :deep(.el-input-number) { width: 130px; }
.add-option { width: 100%; }
</style>
