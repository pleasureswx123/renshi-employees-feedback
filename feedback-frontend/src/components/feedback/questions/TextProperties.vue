<script setup>
import { nextTick, ref } from 'vue'

const props = defineProps({ question: { type: Object, required: true } })
const emit = defineEmits(['change'])
const formRef = ref()

function changeMaxLength(value) {
  emit('change', { ...props.question, config: { maxLength: value ?? 1000 }, isScored: false })
}

async function validate() {
  await nextTick()
  return formRef.value?.validate()
}

defineExpose({ validate })
</script>

<template>
  <el-form ref="formRef" :model="question" label-position="top">
    <el-form-item label="最大字数">
      <el-input-number
        :model-value="question.config.maxLength"
        :min="1"
        :max="5000"
        :precision="0"
        controls-position="right"
        @change="changeMaxLength"
      />
    </el-form-item>
    <el-alert title="问答题不参与正式计分，也不能绑定评价指标。" type="info" :closable="false" />
  </el-form>
</template>
