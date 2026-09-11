<script setup>
import { nextTick, reactive, ref } from 'vue'
import CircleIcon from '@iconify-vue/lucide/circle'
import PlusIcon from '@iconify-vue/lucide/plus'
import TrashIcon from '@iconify-vue/lucide/trash-2'

import { decimalToNumber, normalizeDecimal } from '@/utils/fixedDecimal'
import { createStableCode } from '@/utils/stableCode'

const props = defineProps({ question: { type: Object, required: true }, disabled: { type: Boolean, default: false } })
const emit = defineEmits(['change'])
const formRef = ref()
const batchVisible = ref(false)
const batchFormRef = ref()
const batchForm = reactive({ text: '' })
const batchPending = ref(false)

function parseBatchOptions(text) {
  const lines = text.split(/\r?\n/).map(line => line.trim()).filter(Boolean)
  if (lines.length < 2 || lines.length > 100) throw new Error('请填写 2 至 100 个选项')
  return lines.map((line, index) => {
    const [label, suppliedScore, ...extra] = line.split('|').map(item => item.trim())
    const rawScore = suppliedScore || '2'
    if (!label || label.length > 500 || extra.length) throw new Error(`第 ${index + 1} 行选项格式不正确`)
    if (!/^\d+(?:\.0+)?$/.test(rawScore) || Number(rawScore) < 1 || Number(rawScore) > 99999999) {
      throw new Error(`第 ${index + 1} 行分值必须是 1 至 99999999 的整数`)
    }
    return { optionLabel: label, score: normalizeDecimal(rawScore) }
  })
}

function validateBatch(_rule, value, callback) {
  try { parseBatchOptions(value); callback() } catch (error) { callback(error) }
}

function validateScore(_rule, value, callback) {
  callback(isValidScore(value) ? undefined : new Error(`分值 ${value} 无效，请设置大于等于1的整数`))
}

function isValidScore(value) {
  const score = Number(value)
  return Number.isInteger(score) && score >= 1 && score <= 99999999
}

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
        score: '2.0000',
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

async function applyBatchOptions() {
  if (props.disabled || batchPending.value) return
  batchPending.value = true
  const questionCode = props.question.questionCode
  try {
    await batchFormRef.value.validate()
    if (!batchVisible.value || props.disabled || props.question.questionCode !== questionCode) return
    const options = parseBatchOptions(batchForm.text).map((option, index) => ({
        ...option,
        optionId: null,
        optionCode: createStableCode('O'),
        requiresReason: false,
        sortOrder: index + 1
    }))
    changeQuestion({ options })
    batchVisible.value = false
  } catch {
    // 校验失败时保留输入，由表单展示具体行号和原因。
  } finally {
    batchPending.value = false
  }
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
      <el-button link type="primary" :disabled="disabled" @click="batchVisible = true">批量设置</el-button>
    </div>
    <el-form ref="formRef" :model="question" :disabled="disabled" label-position="top">
      <div v-for="(option, index) in question.options" :key="option.optionCode" class="option-editor">
        <CircleIcon width="16" height="16" class="option-marker" aria-hidden="true" />
        <el-form-item
          class="option-label"
          :label="`选项 ${index + 1}`"
          :prop="`options.${index}.optionLabel`"
          :rules="[{ required: true, whitespace: true, message: '选项文本不能为空', trigger: 'blur' }]"
        >
          <el-input
            :model-value="option.optionLabel"
            maxlength="500"
            @input="changeOption(index, { optionLabel: $event })"
          />
        </el-form-item>
          <el-form-item
            :label="`选项 ${index + 1} 分值`" :prop="`options.${index}.score`"
            :rules="[{ validator: validateScore, trigger: 'change' }]"
            :error="isValidScore(option.score) ? '' : `原分值为 ${option.score}，请设置大于等于1的整数`"
            class="option-score"
          >
            <el-input-number
              :model-value="isValidScore(option.score) ? decimalToNumber(option.score) : undefined"
              :min="1"
              :max="99999999"
              :precision="0"
              :step="1"
              step-strictly
              :aria-label="`选项 ${index + 1} 分值`"
              controls-position="right"
              @update:model-value="changeOption(index, { score: normalizeDecimal($event ?? 2) })"
            />
          </el-form-item>
          <el-form-item :label="`选项 ${index + 1} 要求说明`" class="option-reason">
            <el-checkbox
              :model-value="option.requiresReason"
              :aria-label="`选项 ${index + 1} 要求说明`"
              @change="changeOption(index, { requiresReason: $event })"
            >需说明</el-checkbox>
          </el-form-item>
          <el-button
            type="danger"
            text
            class="remove-option"
            :aria-label="`删除选项 ${index + 1}`"
            :title="question.options.length <= 2 ? '至少保留两个选项' : '删除选项'"
            :disabled="disabled || question.options.length <= 2"
            @click="removeOption(index)"
          ><TrashIcon width="16" height="16" aria-hidden="true" /></el-button>
      </div>
      <el-button class="add-option" link type="primary" :disabled="disabled" @click="addOption"><PlusIcon width="16" height="16" aria-hidden="true" />增加选项</el-button>
    </el-form>

    <el-dialog v-model="batchVisible" title="批量设置选项" width="min(520px, 94vw)" append-to-body>
      <el-form ref="batchFormRef" :model="batchForm" :disabled="batchPending" label-position="top">
        <el-form-item prop="text" :rules="[{ validator: validateBatch, trigger: 'blur' }]" label="每行一个选项，可用“选项文字 | 分值”格式；分值为正整数，省略时默认2分，应用后替换当前选项">
          <el-input
            v-model="batchForm.text"
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
          :loading="batchPending"
          :disabled="disabled"
          @click="applyBatchOptions"
        >应用选项</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.option-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px; font-size: 13px; }
.option-editor { display: grid; grid-template-columns: 16px minmax(90px, 1fr) 110px 76px 28px; align-items: start; gap: 8px; margin-bottom: 16px; }
.option-marker { margin-top: 8px; color: var(--fb-text-disabled, #a8abb2); }
.option-editor:deep(.el-form-item) { min-width: 0; margin-bottom: 0; }
.option-editor:deep(.el-form-item__label) { position: absolute; width: 1px; height: 1px; margin: -1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
.option-score:deep(.el-input-number) { width: 100%; }
.option-reason:deep(.el-checkbox__label) { padding-left: 5px; font-size: 12px; }
.remove-option { width: 28px; height: 32px; padding: 0; }
.add-option { margin-left: 24px; gap: 5px; }
@container (max-width: 500px) {
  .option-editor { grid-template-columns: 16px minmax(80px, 1fr) 100px 28px; }
  .option-reason { grid-column: 2 / 4; grid-row: 2; }
  .remove-option { grid-column: 4; grid-row: 1; }
}
</style>
