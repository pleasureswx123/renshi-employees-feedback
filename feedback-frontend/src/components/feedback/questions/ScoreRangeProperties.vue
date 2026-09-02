<script setup>
import { computed, nextTick, ref } from 'vue'

import { decimalToNumber, normalizeDecimal } from '@/utils/fixedDecimal'

const props = defineProps({ question: { type: Object, required: true } })
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
  <el-form ref="formRef" :model="question" label-position="top">
    <template v-if="isStar">
      <el-form-item label="星级数量">
        <el-input-number
          :model-value="decimalToNumber(question.maxScore)"
          :min="2"
          :max="10"
          :precision="0"
          @change="changeStarCount"
        />
      </el-form-item>
      <el-alert title="未点击任何星级时保持未作答，不会把0误记为答案。" type="info" :closable="false" />
    </template>
    <template v-else>
      <div class="range-row">
        <el-form-item label="最低分">
          <el-input-number
            :model-value="decimalToNumber(question.minScore)"
            :min="0"
            :precision="question.decimalPlaces"
            @change="changeQuestion({ minScore: decimalValue($event, 0) })"
          />
        </el-form-item>
        <el-form-item label="最高分">
          <el-input-number
            :model-value="decimalToNumber(question.maxScore)"
            :min="0.0001"
            :precision="question.decimalPlaces"
            @change="changeQuestion({ maxScore: decimalValue($event, 100) })"
          />
        </el-form-item>
      </div>
      <el-form-item label="小数位数">
        <el-input-number
          :model-value="question.decimalPlaces"
          :min="0"
          :max="4"
          :precision="0"
          @change="changeQuestion({ decimalPlaces: $event ?? 0 })"
        />
      </el-form-item>
      <el-form-item v-if="isSlider" label="滑动步长">
        <el-input-number
          :model-value="decimalToNumber(question.config.step)"
          :min="0.0001"
          :precision="question.decimalPlaces"
          @change="changeConfig({ step: decimalValue($event, 1) })"
        />
      </el-form-item>
      <el-form-item label="默认值（留空表示不预填答案）">
        <el-input-number
          :model-value="question.config.defaultValue == null ? null : decimalToNumber(question.config.defaultValue)"
          :min="decimalToNumber(question.minScore)"
          :max="decimalToNumber(question.maxScore)"
          :precision="question.decimalPlaces"
          clearable
          @change="changeConfig({ defaultValue: $event == null ? null : decimalValue($event, 0) })"
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
.range-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.range-row :deep(.el-input-number), :deep(.el-input-number) { width: 100%; }
</style>
