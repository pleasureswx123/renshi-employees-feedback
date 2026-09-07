<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, AriaComponent } from 'echarts/components'
import { SVGRenderer } from 'echarts/renderers'
echarts.use([BarChart, GridComponent, TooltipComponent, AriaComponent, SVGRenderer])
const props = defineProps({ rows: { type: Array, default: () => [] }, metric: { type: [String, Number], default: 'total' }, title: { type: String, default: '最终得分' }, weight: { type: String, default: '' } })
const emit = defineEmits(['source'])
const host = ref()
const person = ref(null)
let chart, resizeObserver, themeObserver
const valueOf = row => props.metric === 'total' ? row.score : row.indicators?.find(item => item.indicatorId === props.metric)?.score
const missing = computed(() => props.rows.filter(row => valueOf(row) == null))
function showSource(row) { if (row) emit('source', { row, key: props.metric === 'total' ? 'total' : `i-${props.metric}` }) }
function render() {
  if (!chart || !host.value) return
  const style = getComputedStyle(host.value)
  const textColor = style.getPropertyValue('--el-text-color-primary').trim() || '#303133'
  const borderColor = style.getPropertyValue('--el-border-color-lighter').trim() || '#ebeef5'
  const blue = style.getPropertyValue('--el-color-primary').trim() || '#409eff'
  chart.setOption({
    animation: false,
    aria: { enabled: true, description: `当前页人员的${props.title}，百分制，缺失数据不按零分展示。也可使用下方人员选择查看得分来源。` },
    grid: { left: 12, right: 70, top: 25, bottom: 32, containLabel: true },
    tooltip: { trigger: 'item', renderMode: 'richText', confine: true, formatter: params => {
      const row = props.rows[params.dataIndex]
      return `${row.targetName} · ${row.targetDeptName || '未设置部门'}\n${props.title}：${valueOf(row) ?? '数据不足'}\n已提交 ${row.submittedCount}/${row.expectedCount} 份${row.hasMissingData ? ' · 存在缺失数据' : ''}\n${row.onlySelfEvaluation ? '仅自评计分' : '按他评加权计分'}\n点击查看公式与来源`
    } },
    xAxis: { type: 'value', min: 0, max: 100, interval: 20, axisLabel: { color: textColor }, splitLine: { lineStyle: { color: borderColor } } },
    yAxis: { type: 'category', inverse: true, data: props.rows.map(row => String(row.targetUserId)), axisTick: { show: false }, axisLine: { show: false }, axisLabel: { color: textColor, width: 150, overflow: 'truncate', formatter: (_value, index) => props.rows[index].targetName } },
    series: [{ type: 'bar', name: props.title, barMaxWidth: 26, itemStyle: { color: blue, borderRadius: [0, 5, 5, 0] }, label: { show: true, position: 'right', color: textColor, formatter: params => valueOf(props.rows[params.dataIndex]) ?? '' }, data: props.rows.map(row => valueOf(row) == null ? null : Number(valueOf(row))) }]
  }, true)
  chart.resize()
}
watch(() => props.rows, () => { if (!props.rows.some(row => row.targetUserId === person.value)) person.value = props.rows[0]?.targetUserId ?? null }, { immediate: true })
watch([() => props.rows, () => props.metric], async () => { await nextTick(); render() }, { deep: true })
onMounted(() => {
  chart = echarts.init(host.value, null, { renderer: 'svg' })
  chart.on('click', params => { if (params.componentType === 'series') showSource(props.rows[params.dataIndex]) })
  resizeObserver = new ResizeObserver(() => chart?.resize())
  resizeObserver.observe(host.value)
  themeObserver = new MutationObserver(render)
  themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['class', 'style', 'data-theme'] })
  render()
})
onBeforeUnmount(() => { resizeObserver?.disconnect(); themeObserver?.disconnect(); chart?.dispose(); chart = null })
</script>

<template>
  <section class="score-chart">
    <header class="chart-heading"><h3>{{ title }}</h3><span v-if="weight">指标权重 {{ weight }}%</span></header>
    <div class="chart-scroll"><div ref="host" :style="{ height: `${Math.max(260, rows.length * 48 + 70)}px` }" class="chart-host" /></div>
    <el-empty v-if="!rows.length" description="当前筛选下没有可展示的人员" :image-size="70" />
    <p v-if="missing.length">数据不足（不按零分绘制）：{{ missing.map(row => row.targetName).join('、') }}</p>
    <div v-if="rows.length" class="chart-toolbar"><label :for="`chart-person-${metric}`">查看人员</label><el-select :id="`chart-person-${metric}`" v-model="person" filterable aria-label="查看人员" style="width: 200px"><el-option v-for="row in rows" :key="row.targetUserId" :value="row.targetUserId" :label="`${row.targetName} · ${row.targetDeptName || '未设置部门'}`" /></el-select><el-button @click="showSource(rows.find(row => row.targetUserId === person))">查看得分来源</el-button></div>
  </section>
</template>

<style scoped>
.score-chart { min-width: 0; padding: 20px; border: 1px solid var(--el-border-color-lighter); border-radius: 12px; }
.chart-heading { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
.chart-heading h3 { margin: 0; font-size: 17px; }
.chart-heading span { color: var(--fb-text-muted, #64748b); font-size: 13px; }
.chart-toolbar { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; font-size: 14px; }
p, .chart-toolbar span { color: var(--fb-text-muted, #64748b); font-size: 13px; line-height: 1.7; }
.chart-scroll { max-height: 460px; overflow: auto; margin: 18px 0; }
.chart-host { width: 100%; min-width: 300px; }
</style>
