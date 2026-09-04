<script setup>
import { computed } from 'vue'

import { decimalToNumber, normalizeDecimal, sumDecimals } from '@/utils/fixedDecimal'
import { getQuestionTypeDefinition } from './questions/questionTypeRegistry'

const props = defineProps({
  indicators: { type: Array, required: true },
  questions: { type: Array, required: true }
})
const emit = defineEmits(['add', 'change', 'delete', 'move', 'set-bindings'])
const totalWeight = computed(() => sumDecimals(props.indicators.map(indicator => indicator.weight)))
</script>

<template>
  <section class="indicator-panel">
    <div class="indicator-heading">
      <div>
        <strong>评价指标</strong>
        <p>一个计分题最多绑定一个指标；发布前权重合计须为100.0000。</p>
      </div>
      <el-button type="primary" plain @click="emit('add')">增加指标</el-button>
    </div>
    <el-alert
      :title="`当前权重合计：${totalWeight}`"
      :type="totalWeight === '100.0000' ? 'success' : 'warning'"
      :closable="false"
      show-icon
    />
    <el-empty v-if="!indicators.length" description="尚未配置评价指标" :image-size="72" />
    <article v-for="(indicator, index) in indicators" :key="indicator.indicatorCode" class="indicator-card">
      <div class="indicator-card-heading">
        <strong>指标 {{ index + 1 }}</strong>
        <div>
          <el-button link :disabled="index === 0" @click="emit('move', indicator.indicatorCode, -1)">上移</el-button>
          <el-button link :disabled="index === indicators.length - 1" @click="emit('move', indicator.indicatorCode, 1)">下移</el-button>
          <el-button link type="danger" @click="emit('delete', indicator.indicatorCode)">删除</el-button>
        </div>
      </div>
      <el-form :model="indicator" label-position="top">
        <div class="indicator-form-row">
          <el-form-item label="指标名称" required>
            <el-input
              :model-value="indicator.indicatorName"
              maxlength="100"
              @input="emit('change', indicator.indicatorCode, { indicatorName: $event })"
            />
          </el-form-item>
          <el-form-item label="权重（%）" required>
            <el-input-number
              :model-value="decimalToNumber(indicator.weight)"
              :min="0"
              :max="100"
              :precision="4"
              controls-position="right"
              @change="emit('change', indicator.indicatorCode, { weight: normalizeDecimal($event ?? 0) })"
            />
          </el-form-item>
        </div>
        <el-form-item label="指标说明">
          <el-input
            :model-value="indicator.description"
            type="textarea"
            :rows="2"
            maxlength="5000"
            @input="emit('change', indicator.indicatorCode, { description: $event })"
          />
        </el-form-item>
        <el-form-item label="绑定计分题">
          <el-select
            :model-value="indicator.questionCodes"
            multiple
            filterable
            collapse-tags
            collapse-tags-tooltip
            placeholder="选择该指标包含的计分题"
            @change="emit('set-bindings', indicator.indicatorCode, $event)"
          >
            <el-option
              v-for="question in questions"
              :key="question.questionCode"
              :label="question.title.trim() || `${getQuestionTypeDefinition(question.questionType)?.label} · 待填写`"
              :value="question.questionCode"
            />
          </el-select>
        </el-form-item>
      </el-form>
    </article>
  </section>
</template>

<style scoped>
.indicator-panel { display: grid; gap: 16px; }
.indicator-heading, .indicator-card-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.indicator-heading p { margin: 5px 0 0; color: #64748b; font-size: 13px; }
.indicator-card { padding: 16px; border: 1px solid #e5e7eb; border-radius: 9px; background: #fff; }
.indicator-card-heading { margin-bottom: 12px; }
.indicator-form-row { display: grid; grid-template-columns: minmax(0, 1fr) 150px; gap: 12px; }
:deep(.el-select), :deep(.el-input-number) { width: 100%; }
@media (max-width: 720px) { .indicator-form-row { grid-template-columns: 1fr; } }
</style>
