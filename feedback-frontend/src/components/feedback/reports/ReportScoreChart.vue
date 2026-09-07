<script setup>
import { computed } from 'vue'
import ScoreBarChart from './ScoreBarChart.vue'
const props = defineProps({ rows: { type: Array, default: () => [] } })
defineEmits(['source'])
const indicators = computed(() => [...new Map(props.rows.flatMap(row => row.indicators || []).map(item => [item.indicatorId, item])).values()])
</script>

<template>
  <section class="report-charts">
    <p>当前页 {{ rows.length }} 人 · 最终得分与全部指标同时展示，统一使用 0–100 分刻度和团队排名顺序。筛选、翻页同步更新，点击条形可查看得分来源。</p>
    <el-empty v-if="!rows.length" description="当前筛选下没有可展示的人员" :image-size="70" />
    <template v-else>
      <ScoreBarChart :rows="rows" title="最终得分" @source="$emit('source', $event)" />
      <div class="indicator-charts"><ScoreBarChart v-for="item in indicators" :key="item.indicatorId" :rows="rows" :metric="item.indicatorId" :title="item.indicatorName" :weight="item.weight" @source="$emit('source', $event)" /></div>
    </template>
  </section>
</template>

<style scoped>
.report-charts { display: grid; gap: 20px; min-width: 0; }
.report-charts > p { margin: 0; color: var(--fb-text-muted, #64748b); font-size: 13px; line-height: 1.7; }
.indicator-charts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 20px; }
@media (max-width: 1000px) { .indicator-charts { grid-template-columns: minmax(0, 1fr); } }
</style>
