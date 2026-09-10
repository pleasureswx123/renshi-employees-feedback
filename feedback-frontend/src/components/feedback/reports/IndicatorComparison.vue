<script setup>
import { computed, ref, watch } from 'vue'
const props = defineProps({ rows: { type: Array, default: () => [] }, selectedIndicator: { type: [String, Number], default: null }, showToolbar: { type: Boolean, default: true } })
defineEmits(['detail', 'source'])
const selected = ref('all')
const indicators = computed(() => [...new Map(props.rows.flatMap(row => row.indicators || []).map(item => [item.indicatorId, item])).values()])
const activeIndicator = computed(() => props.selectedIndicator ?? selected.value)
const visibleIndicators = computed(() => activeIndicator.value === 'all' ? indicators.value : indicators.value.filter(item => item.indicatorId === activeIndicator.value))
const relationColumns = computed(() => {
  const groups = [...new Map(props.rows.flatMap(row => [...(row.relations || []), ...(row.indicators || []).flatMap(item => item.relations || [])]).map(item => [item.relationId, item])).values()]
  const kinds = [
    { label: '上级', matches: item => ['SUPERVISOR', 'SUPERIOR'].includes(item.relationType) || item.relationName === '上级' },
    { label: '同级', matches: item => item.relationType === 'PEER' || item.relationName === '同级' },
    { label: '自己', matches: item => item.relationType === 'SELF' }
  ]
  return [
    ...kinds.flatMap(kind => {
      const matches = groups.filter(kind.matches)
      return matches.length ? matches.map(item => ({ ...item, label: kind.label })) : [{ relationId: `missing-${kind.label}`, label: kind.label }]
    }),
    ...groups.filter(item => !kinds.some(kind => kind.matches(item))).map(item => ({ ...item, label: item.relationName }))
  ]
})
const totalRelationScore = (row, group) => {
  const coverage = row.relations?.find(item => item.relationId === group.relationId)
  if (!coverage || coverage.status === 'NOT_APPLICABLE') return '—'
  return scoreText(row.relationScores?.[group.relationId])
}
const indicator = (row, id) => row.indicators?.find(item => item.indicatorId === id)
const relation = (row, indicatorId, id) => indicator(row, indicatorId)?.relations?.find(item => item.relationId === id)
const relationWeight = (indicatorId, relationId) => props.rows
  .map(row => relation(row, indicatorId, relationId)?.originalWeight)
  .find(weight => weight !== undefined && weight !== null)
const scoreText = value => value ?? '数据不足'
const statusText = { NOT_APPLICABLE: '未配置', MISSING: '未提交', PARTIAL: '部分提交', COMPLETE: '全部提交' }
watch(indicators, items => { if (selected.value !== 'all' && !items.some(item => item.indicatorId === selected.value)) selected.value = 'all' })
</script>

<template>
  <div class="indicator-comparison">
    <div v-if="showToolbar" class="comparison-toolbar"><label for="report-indicator">查看维度</label><el-select id="report-indicator" v-model="selected" aria-label="查看维度" style="width: 260px"><el-option label="全部指标" value="all" /><el-option v-for="item in indicators" :key="item.indicatorId" :label="item.indicatorName" :value="item.indicatorId" /></el-select></div>
    <p class="comparison-help">一行一人，总得分后的上级、同级、自己分别为全部指标对应关系得分之和 ÷ 指标数，不按指标权重加权，不参与总得分计算。每个指标下展示各评价关系得分与综合平均，均为百分制；综合平均沿用发布时的关系权重加权计分，自评通常仅作参考。横向滚动可查看全部指标，点击分数可查看公式与得分来源。</p>
    <el-table :key="activeIndicator" :data="rows" border stripe max-height="620" empty-text="没有匹配的被评价人" class="comparison-table">
      <el-table-column prop="targetDeptName" label="部门" fixed="left" width="140" show-overflow-tooltip />
      <el-table-column label="被评价人" fixed="left" width="130"><template #default="{ row }"><strong>{{ row.targetName }}</strong><small v-if="row.onlySelfEvaluation">仅自评 · 以自评计分</small></template></el-table-column>
      <el-table-column label="总得分" fixed="left" width="115"><template #default="{ row }"><el-button link class="final-score" @click="$emit('source', { row, key: 'total' })">{{ scoreText(row.score) }}</el-button></template></el-table-column>
      <el-table-column v-for="group in relationColumns" :key="`total-${group.relationId}`" :label="group.label" width="100" align="center"><template #default="{ row }"><el-button v-if="row.relationScores?.[group.relationId] != null" link class="relation-score" @click="$emit('source', { row, key: `r-${group.relationId}-average` })">{{ totalRelationScore(row, group) }}</el-button><span v-else>{{ totalRelationScore(row, group) }}</span></template></el-table-column>
      <el-table-column v-for="item in visibleIndicators" :key="item.indicatorId" :label="item.indicatorName" header-align="center">
        <template #header><strong>{{ item.indicatorName }}</strong><span class="indicator-weight">权重 {{ item.weight }}%</span></template>
        <el-table-column v-for="group in relationColumns" :key="group.relationId" :label="group.label" width="100" align="center">
          <template #header>
            <span>{{ group.label }}</span>
            <small v-if="relationWeight(item.indicatorId, group.relationId) !== undefined" class="relation-weight" title="发布时配置的关系权重；个人实际计分权重见分数提示">权重 {{ relationWeight(item.indicatorId, group.relationId) }}%</small>
          </template>
          <template #default="{ row }">
            <template v-if="relation(row, item.indicatorId, group.relationId)">
              <el-tooltip placement="top" :show-after="200"><template #content><div>{{ statusText[relation(row, item.indicatorId, group.relationId).status] }} · {{ relation(row, item.indicatorId, group.relationId).submittedCount }}/{{ relation(row, item.indicatorId, group.relationId).expectedCount }} 份</div><div>实际权重 {{ relation(row, item.indicatorId, group.relationId).effectiveWeight }}%</div><div v-if="relation(row, item.indicatorId, group.relationId).missingAnswerCount">计分题漏答 {{ relation(row, item.indicatorId, group.relationId).missingAnswerCount }} 次</div></template>
                <el-button link class="relation-score" @click="$emit('source', { row, key: `i-${item.indicatorId}-r-${group.relationId}` })">{{ relation(row, item.indicatorId, group.relationId).status === 'NOT_APPLICABLE' ? '—' : scoreText(relation(row, item.indicatorId, group.relationId).score) }}</el-button>
              </el-tooltip>
              <small v-if="relation(row, item.indicatorId, group.relationId).status === 'PARTIAL'">部分提交</small>
              <small v-else-if="relation(row, item.indicatorId, group.relationId).status === 'MISSING'">未提交</small>
              <small v-if="relation(row, item.indicatorId, group.relationId).missingAnswerCount">有漏答</small>
            </template><span v-else>—</span>
          </template>
        </el-table-column>
        <el-table-column label="综合平均" width="110" align="center" class-name="indicator-final"><template #default="{ row }"><el-button link type="primary" @click="$emit('source', { row, key: `i-${item.indicatorId}` })">{{ scoreText(indicator(row, item.indicatorId)?.score) }}</el-button></template></el-table-column>
      </el-table-column>
      <el-table-column label="完成情况" width="150"><template #default="{ row }">{{ row.submittedCount }}/{{ row.expectedCount }} 份<small v-if="row.hasMissingData">存在缺失数据</small></template></el-table-column>
      <el-table-column label="操作" width="145"><template #default="{ row }"><el-button link type="primary" @click="$emit('detail', row)">查看得分详情</el-button></template></el-table-column>
    </el-table>
  </div>
</template>

<style scoped>
.comparison-toolbar { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.comparison-toolbar label { font-size: 14px; }
.comparison-help { color: var(--fb-text-muted, #64748b); font-size: 13px; line-height: 1.7; margin: 12px 0 20px; }
small { display: block; margin-top: 6px; font-size: 12px; font-weight: normal; color: var(--fb-text-muted, #64748b); line-height: 1.6; }
.final-score { color: var(--el-color-primary); font-size: 18px; }
.comparison-table { font-variant-numeric: tabular-nums; }
.comparison-table :deep(.el-table__cell) { padding-block: 12px; }
.indicator-weight { margin-left: 10px; font-size: 12px; font-weight: normal; color: var(--fb-text-muted, #64748b); }
.relation-weight { margin-top: 2px; white-space: nowrap; }
.comparison-table :deep(.indicator-final) { background: var(--el-color-primary-light-9); }
.relation-score { display: inline-block; cursor: help; font-variant-numeric: tabular-nums; }
</style>
