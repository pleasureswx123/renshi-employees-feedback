<script setup>
import { computed, nextTick, ref } from 'vue'

import { decimalToNumber, normalizeDecimal } from '@/utils/fixedDecimal'

const props = defineProps({ question: { type: Object, required: true }, disabled: { type: Boolean, default: false } })
const emit = defineEmits(['change'])
const formRef = ref()
const isStar = computed(() => props.question.questionType === 'STAR_RATING')
const isSlider = computed(() => props.question.questionType === 'SLIDER')

function decimalValue(value, fallback) {
  try {
    return normalizeDecimal(value ?? fallback)
  } catch {
    return normalizeDecimal(fallback)
  }
}

function changeQuestion(patch) {
  emit('change', { ...props.question, ...patch })
}

function changeConfig(patch) {
  changeQuestion({ config: { ...props.question.config, ...patch } })
}

function changeStarCount(value) {
  changeQuestion({ minScore: '1.0000', maxScore: normalizeDecimal(value ?? 5), decimalPlaces: 0 })
}

async function validate() {
  await nextTick()
  return formRef.value?.validate()
}

defineExpose({ validate })
</script>

<template>
  <el-form ref="formRef" :model="question" :disabled="disabled" label-position="top" class="score-settings">
    <template v-if="isStar">
      <el-form-item label="星级数量">
        <el-input-number
          :model-value="decimalToNumber(question.maxScore)"
          :min="2"
          :max="10"
          :precision="0"
          @update:model-value="changeStarCount"
        />
      </el-form-item>
      <p class="setting-hint">可设置 2–10 颗星，每颗星对应 1 分。</p>
    </template>
    <template v-else>
      <div class="range-row">
        <el-form-item label="最低分">
          <el-input-number
            :model-value="decimalToNumber(question.minScore)"
            :min="0"
            :precision="question.decimalPlaces"
            @update:model-value="changeQuestion({ minScore: decimalValue($event, 0) })"
          />
        </el-form-item>
        <el-form-item label="最高分">
          <el-input-number
            :model-value="decimalToNumber(question.maxScore)"
            :min="10 ** -question.decimalPlaces"
            :precision="question.decimalPlaces"
            @update:model-value="changeQuestion({ maxScore: decimalValue($event, 100) })"
          />
        </el-form-item>
      </div>
      <el-form-item label="小数位数">
        <el-input-number
          :model-value="question.decimalPlaces"
          :min="0"
          :max="4"
          :precision="0"
          @update:model-value="changeQuestion({ decimalPlaces: $event ?? 0 })"
        />
      </el-form-item>
      <el-form-item v-if="isSlider" label="滑动步长">
        <el-input-number
          :model-value="decimalToNumber(question.config.step)"
          :min="10 ** -question.decimalPlaces"
          :precision="question.decimalPlaces"
          @update:model-value="changeConfig({ step: decimalValue($event, 1) })"
        />
      </el-form-item>
      <el-form-item label="默认值（选填）">
        <el-input-number
          :model-value="question.config.defaultValue == null ? null : decimalToNumber(question.config.defaultValue)"
          :min="decimalToNumber(question.minScore)"
          :max="decimalToNumber(question.maxScore)"
          :precision="question.decimalPlaces"
          clearable
          @update:model-value="changeConfig({ defaultValue: $event == null ? null : decimalValue($event, 0) })"
        />
      </el-form-item>
      <el-alert
        v-if="isSlider"
        title="预览中必须实际移动滑块或使用方向键，才会记录答案。"
        type="info"
        :closable="false"
      />
    </template>
  </el-form>
</template>

<style scoped>
.score-settings { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 16px; max-width: 560px; }
.range-row { display: contents; }
.setting-hint { margin: 0; align-self: center; color: var(--fb-text-muted, #909399); font-size: 12px; }
.score-settings:deep(.el-alert) { grid-column: 1 / -1; }
.range-row:deep(.el-input-number), :deep(.el-input-number) { width: 100%; }
</style>
