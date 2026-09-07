<script setup>
import ArrowDownIcon from '@iconify-vue/lucide/arrow-down'
import ArrowUpIcon from '@iconify-vue/lucide/arrow-up'
import TrashIcon from '@iconify-vue/lucide/trash-2'
import { computed } from 'vue'

import { DECIMAL_FACTOR, decimalToNumber, normalizeDecimal, sumDecimals, toScaledInteger } from '@/utils/fixedDecimal'
import { getQuestionTypeDefinition } from './questions/questionTypeRegistry'

const props = defineProps({
  indicators: { type: Array, required: true },
  questions: { type: Array, required: true },
  pages: { type: Array, default: () => [] }
})
const emit = defineEmits(['add', 'change', 'delete', 'move', 'set-bindings', 'set-question-indicator', 'locate-question'])
const unboundQuestions = computed(() => {
  const boundCodes = new Set(props.indicators.flatMap(indicator => indicator.questionCodes))
  let number = 0
  // 编号按整卷计算，问答题及不计分题也占题号，但不进入待绑定清单。
  return props.pages.flatMap((page, pageIndex) => page.questions.map(question => ({
    question, number: ++number, pageNumber: pageIndex + 1, pageTitle: page.pageTitle
  }))).filter(({ question }) => question.isScored && question.questionType !== 'TEXT' && !boundCodes.has(question.questionCode))
})
const totalWeight = computed(() => sumDecimals(props.indicators.map(indicator => indicator.weight)))
const weightState = computed(() => {
  const total = toScaledInteger(totalWeight.value)
  const target = 100 * DECIMAL_FACTOR
  if (total > target) {
    return { type: 'error', message: `超出${(total - target) / DECIMAL_FACTOR}%` }
  }
  if (total < target) {
    return { type: 'warning', message: `还差${(target - total) / DECIMAL_FACTOR}%` }
  }
  return { type: 'success', message: '权重达标' }
})
</script>

<template>
  <section class="indicator-panel">
    <div class="indicator-heading">
      <div class="indicator-heading-label">
        <strong>评价指标</strong>
        <el-popover title="指标与权重怎么算？" trigger="click" placement="left-start" :width="320">
          <template #reference>
            <el-button link type="primary" size="small">查看示例</el-button>
          </template>
          <div class="indicator-help">
            <p>把同一方面的题目绑定到一个指标，例如“工作能力”。</p>
            <p>指标分＝这些题目的得分合计 ÷ 满分合计 × 100。</p>
            <div class="indicator-help-example">
              <p>工作能力：80分 × 60%权重＝48分</p>
              <p>协作态度：60分 × 40%权重＝24分</p>
              <strong>最终得分：48＋24＝72分</strong>
            </div>
            <p class="indicator-help-rule">每道计分题绑定一个指标，所有指标权重合计为100%。</p>
          </div>
        </el-popover>
      </div>
      <el-button type="primary" plain size="small" @click="emit('add')">增加指标</el-button>
    </div>
    <p class="indicator-hint">指标是评价的方面，如能力、协作；权重决定它占总分多少。</p>
    <el-alert
      class="weight-summary"
      :type="weightState.type"
      :closable="false"
      show-icon
    >
      <template #title>
        <span>合计</span>
        <strong>{{ decimalToNumber(totalWeight) }}%</strong>
        <span class="weight-target">/ 100%</span>
        <span class="weight-status" :title="weightState.type === 'error' ? '请减少指标权重，使合计为100%' : undefined">{{ weightState.message }}</span>
      </template>
    </el-alert>
    <el-empty v-if="!indicators.length" description="尚未配置评价指标" :image-size="72" />
    <article v-for="(indicator, index) in indicators" :key="indicator.indicatorCode" class="indicator-card">
      <div class="indicator-card-heading">
        <strong>指标 {{ index + 1 }}</strong>
        <div class="indicator-actions" role="group" :aria-label="`指标 ${index + 1} 操作`">
          <el-tooltip content="上移指标" :trigger="['hover', 'focus']" :trigger-keys="[]" :enterable="false">
            <el-button text size="small" :disabled="index === 0" :aria-label="`上移指标 ${index + 1}`" @click="emit('move', indicator.indicatorCode, -1)"><ArrowUpIcon width="14" height="14" aria-hidden="true" /></el-button>
          </el-tooltip>
          <el-tooltip content="下移指标" :trigger="['hover', 'focus']" :trigger-keys="[]" :enterable="false">
            <el-button text size="small" :disabled="index === indicators.length - 1" :aria-label="`下移指标 ${index + 1}`" @click="emit('move', indicator.indicatorCode, 1)"><ArrowDownIcon width="14" height="14" aria-hidden="true" /></el-button>
          </el-tooltip>
          <el-tooltip content="删除指标" :trigger="['hover', 'focus']" :trigger-keys="[]" :enterable="false">
            <el-button text size="small" type="danger" :aria-label="`删除指标 ${index + 1}`" @click="emit('delete', indicator.indicatorCode)"><TrashIcon width="14" height="14" aria-hidden="true" /></el-button>
          </el-tooltip>
        </div>
      </div>
      <el-form :model="indicator" label-position="top" size="small">
        <div class="indicator-form-row">
          <el-form-item label="指标名称" required>
            <el-input
              :model-value="indicator.indicatorName"
              maxlength="100"
              @input="emit('change', indicator.indicatorCode, { indicatorName: $event })"
            />
          </el-form-item>
          <el-form-item label="权重（%）" required>
            <!-- 显示不补零，变更时仍通过统一定点工具规范为四位精度。 -->
            <el-input-number
              :model-value="decimalToNumber(indicator.weight)"
              :min="0"
              :max="100"
              controls-position="right"
              @change="emit('change', indicator.indicatorCode, { weight: normalizeDecimal($event ?? 0) })"
            />
          </el-form-item>
        </div>
        <el-form-item label="指标说明" class="indicator-description">
          <el-input
            :model-value="indicator.description"
            type="textarea"
            :autosize="{ minRows: 1, maxRows: 3 }"
            placeholder="补充指标说明（选填）"
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
            :max-collapse-tags="10"
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
    <section v-if="unboundQuestions.length" class="unbound-panel" aria-label="待绑定题目">
      <div class="unbound-heading">
        <strong>待绑定题目</strong>
        <el-tag size="small" type="warning" effect="light" role="status">{{ unboundQuestions.length }} 道</el-tag>
      </div>
      <p class="unbound-hint">{{ indicators.length ? '选择指标即可绑定，点击题目可定位。' : '先增加指标，再为下列题目选择所属指标。' }}</p>
      <div class="unbound-list">
        <article v-for="item in unboundQuestions" :key="item.question.questionCode" class="unbound-item">
          <div class="unbound-question-meta">
            <strong>第 {{ item.number }} 题</strong>
            <span :title="item.pageTitle">第 {{ item.pageNumber }} 页</span>
            <span>{{ getQuestionTypeDefinition(item.question.questionType)?.label }}</span>
          </div>
          <el-button
            link type="primary" class="unbound-question-link"
            :title="item.question.title"
            :aria-label="`定位第${item.number}题：${item.question.title}`"
            @click="emit('locate-question', item.question.questionCode)"
          >{{ item.question.title }}</el-button>
          <el-form :model="item" size="small" label-position="top">
            <el-form-item>
              <el-select
                :model-value="''"
                :aria-label="`为第${item.number}题选择指标`"
                placeholder="选择所属指标"
                :disabled="!indicators.length"
                filterable
                @change="emit('set-question-indicator', item.question.questionCode, $event)"
              >
                <el-option v-for="(indicator, index) in indicators" :key="indicator.indicatorCode" :value="indicator.indicatorCode" :label="indicator.indicatorName.trim() || `未命名指标 ${index + 1}`" />
              </el-select>
            </el-form-item>
          </el-form>
        </article>
      </div>
    </section>
    <p v-else-if="questions.length" class="binding-complete" role="status">计分题已全部绑定</p>
  </section>
</template>

<style scoped>
.indicator-panel { display: grid; gap: 10px; min-width: 0; }
.indicator-heading, .indicator-card-heading { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.indicator-heading strong { color: var(--fb-text-primary, #303133); font-size: 13px; }
.indicator-heading-label { display: flex; align-items: center; gap: 8px; }
.indicator-heading .el-button { flex: none; }
.indicator-hint { margin: -3px 0 0; color: var(--fb-text-muted, #73767a); font-size: 12px; line-height: 1.6; }
.indicator-help { color: var(--fb-text-regular, #606266); font-size: 13px; line-height: 1.7; }
.indicator-help p { margin: 0 0 8px; }
.indicator-help-example { margin: 10px 0; padding: 10px 12px; border-radius: 6px; color: var(--fb-primary-text, #337ecc); background: var(--fb-primary-bg, #ecf5ff); }
.indicator-help-example p { margin-bottom: 4px; }
.indicator-help .indicator-help-rule { margin: 0; color: var(--fb-text-muted, #909399); font-size: 12px; }
.weight-summary { padding: 7px 10px; }
.weight-summary:deep(.el-alert__content) { min-width: 0; }
.weight-summary:deep(.el-alert__title) { display: flex; min-width: 0; align-items: baseline; flex-wrap: wrap; gap: 4px; font-size: 12px; overflow-wrap: anywhere; }
.weight-summary strong { font-size: 15px; font-variant-numeric: tabular-nums; }
.weight-target { color: var(--fb-text-muted, #909399); }
.weight-status { margin-left: 2px; font-weight: 500; }
.unbound-panel { min-width: 0; padding: 10px; border: 1px solid var(--el-color-warning-light-7); border-radius: 8px; background: var(--el-color-warning-light-9); }
.unbound-heading { display: flex; align-items: center; gap: 8px; color: var(--fb-warning-text, #8a5518); font-size: 13px; }
.unbound-hint { margin: 6px 0 8px; color: var(--fb-warning-text, #8a6b43); font-size: 12px; line-height: 1.6; }
.unbound-list { display: grid; gap: 8px; max-height: 240px; overflow-y: auto; scrollbar-gutter: stable; }
.unbound-item { min-width: 0; padding: 8px; border: 1px solid var(--el-color-warning-light-8); border-radius: 6px; background: var(--fb-surface, #fff); }
.unbound-question-meta { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--fb-text-muted, #909399); }
.unbound-question-meta strong { color: var(--fb-text-regular, #606266); }
.unbound-question-link { display: block; width: 100%; height: auto; padding: 5px 0 7px; text-align: left; }
.unbound-question-link:deep(span) { display: -webkit-box; overflow: hidden; -webkit-box-orient: vertical; -webkit-line-clamp: 2; white-space: normal; overflow-wrap: anywhere; line-height: 1.6; }
.unbound-question-link:focus-visible { outline: 2px solid var(--el-color-primary); outline-offset: 1px; }
.unbound-item:deep(.el-form-item) { margin: 0; }
.binding-complete { margin: 0; color: var(--el-color-success-dark-2); font-size: 12px; }
.indicator-card { min-width: 0; padding: 10px 12px 12px; border: 1px solid var(--fb-border, #e5e7eb); border-radius: 8px; background: var(--fb-surface, #fff); }
.indicator-card:focus-within { border-color: var(--el-color-primary-light-5); }
.indicator-card-heading { margin-bottom: 10px; padding-bottom: 7px; border-bottom: 1px solid var(--fb-border, #f0f2f5); }
.indicator-card-heading strong { color: var(--fb-text-regular, #475569); font-size: 12px; font-weight: 600; }
.indicator-actions { display: flex; flex: none; align-items: center; gap: 2px; }
.indicator-actions .el-button { width: 24px; height: 24px; margin: 0; padding: 0; border-radius: 4px; }
.indicator-actions .el-button:focus-visible { outline: 2px solid var(--el-color-primary); outline-offset: 1px; }
.indicator-form-row { display: grid; grid-template-columns: minmax(0, 1fr) 112px; gap: 10px; }
.indicator-card:deep(.el-form-item) { min-width: 0; margin-bottom: 10px; }
.indicator-card:deep(.el-form-item__label) { height: auto; margin-bottom: 4px; padding: 0; color: var(--fb-text-regular, #606266); font-size: 12px; line-height: 18px; }
.indicator-card:deep(.el-form > .el-form-item:last-child) { margin-bottom: 0; }
.indicator-card:deep(.el-form-item__content) { min-width: 0; }
.indicator-description:deep(.el-textarea__inner) { resize: none; }
:deep(.el-select), :deep(.el-input-number) { width: 100%; }
</style>
