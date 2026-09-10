<script setup>
import { trimDecimalZeros, formatFormulaPreview, formatDateTime } from '@/utils/displayFormat'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useProjectReportsStore } from '@/stores/projectReports'
import { usePermissionStore } from '@/stores/permission'
const props = defineProps({ target: { type: Object, required: true } })
const store = useProjectReportsStore()
const permissions = usePermissionStore()
const selectedKey = ref('total')
const selection = ref(null)
const levels = { total: '最终得分', indicator: '指标加权', relation: '关系平均', relation_average: '各指标算术平均', sheet: '答卷换算', question: '题目得分' }
const rows = computed(() => {
  const all = store.source?.rows || []
  const keys = new Set([selectedKey.value])
  return all.filter(row => { if (keys.has(row.key) || keys.has(row.parentKey)) { keys.add(row.key); return true } return false })
})
watch(() => props.target, async target => {
  selection.value = null
  selectedKey.value = target.key || 'total'
  await store.loadSource(target.row.targetUserId)
}, { immediate: true })
const currentSource = computed(() => store.source?.rows?.find(row => row.key === selectedKey.value))
const sheetGroups = computed(() => (store.sourceSheets?.rows || []).filter(row => row.level === 'sheet').map(sheet => ({ ...sheet, questions: store.sourceSheets.rows.filter(row => row.parentKey === sheet.key) })))
const relationSummary = computed(() => store.sourceSheets?.rows?.find(row => row.level === 'relation'))
watch(currentSource, row => {
  selection.value = null
  store.clear('sourceSheets')
  if (row?.level === 'relation' && permissions.hasPermission('feedback:answer:view')) showSheets(row)
})
async function showSheets(row) {
  selection.value = row
  await store.loadSourceSheets(props.target.row.targetUserId, { indicatorId: row.indicatorId, relationId: row.relationId })
}
onBeforeUnmount(() => { store.clear('source'); store.clear('sourceSheets') })
</script>

<template>
  <section class="source-panel">
    <h2>{{ target.row.targetName }} · 得分来源</h2>
    <p>{{ currentSource?.level === 'relation_average' ? '各指标算术平均 → 各指标关系得分 → 答卷换算 → 题目得分' : '最终得分 → 指标加权 → 关系平均 → 答卷换算 → 题目得分' }}</p>
    <el-alert title="公式默认最多显示两位小数，仅供阅读；后台仍按完整精度计算，直接使用显示值复算可能有尾差。可展开“完整精度”核对原始公式。题目得分为原始题分，其余为百分制。" type="info" :closable="false" />
    <el-skeleton v-if="store.loading.source" :rows="6" animated />
    <el-alert v-else-if="store.errors.source" :title="store.errors.source" type="error" :closable="false"><el-button @click="store.loadSource(target.row.targetUserId)">重试</el-button></el-alert>
    <template v-else-if="store.source">
      <p class="source-meta">计算时间：{{ formatDateTime(store.source.calculatedTime) }} · 计分版本：{{ store.source.calculationVersion }} · 已按冻结依据复核</p>
      <el-select v-model="selectedKey" aria-label="查看得分来源" style="width: 100%"><el-option v-for="row in store.source.rows" :key="row.key" :value="row.key" :label="`${row.label} · ${row.result ?? '数据不足'}`" /></el-select>
      <el-table :data="rows" border class="formula-table">
        <el-table-column label="分数含义" min-width="150"><template #default="{ row }"><strong>{{ row.label }}</strong><small>{{ levels[row.level] }}</small></template></el-table-column>
        <el-table-column label="代入实际数值的公式" min-width="280"><template #default="{ row }"><div class="formula">{{ formatFormulaPreview(row.formula) }}</div><small>{{ formatFormulaPreview(row.note) }}</small></template></el-table-column>
        <el-table-column label="结果" width="105"><template #default="{ row }"><strong>{{ row.result ?? '数据不足' }}</strong></template></el-table-column>
        <el-table-column label="核对" width="140"><template #default="{ row }"><el-popover v-if="row.exactResult != null" trigger="click" width="320"><template #reference><el-button link type="primary">完整精度</el-button></template><div class="formula">公式：{{ row.formula }}</div><div class="formula">未舍入结果：{{ row.exactResult }}</div></el-popover><el-button v-if="row.level === 'relation' && permissions.hasPermission('feedback:answer:view')" link type="primary" @click="showSheets(row)">查看答卷公式</el-button></template></el-table-column>
      </el-table>
      <p v-if="!permissions.hasPermission('feedback:answer:view')">逐份答卷及题目计分明细需要原始答案查看权限。</p>
      <template v-if="selection">
        <h3>{{ selection.label }} · 答卷与题目依据</h3>
        <el-skeleton v-if="store.loading.sourceSheets" :rows="5" animated />
        <el-alert v-else-if="store.errors.sourceSheets" :title="store.errors.sourceSheets" type="error" :closable="false"><el-button @click="showSheets(selection)">重试</el-button></el-alert>
        <div v-else-if="store.sourceSheets" class="sheet-breakdown">
          <p>按以下三步核对：先看每题实得分与满分，再看每份答卷换算，最后看这些答卷的平均分。</p>
          <el-empty v-if="!sheetGroups.length" description="该关系没有可换算的已提交答卷" />
          <article v-for="sheet in sheetGroups" :key="sheet.key" class="sheet-card">
            <h3>{{ sheet.label }}</h3>
            <h4>① 哪些题目参与这个指标</h4>
            <el-table :data="sheet.questions" border>
              <el-table-column label="题目" prop="label" min-width="180" />
              <el-table-column label="实得分（原始题分）" width="160"><template #default="{ row }">{{ row.rawScore == null ? '未作答' : trimDecimalZeros(row.rawScore) }}</template></el-table-column>
              <el-table-column label="满分" width="100"><template #default="{ row }">{{ trimDecimalZeros(row.maxScore) }}</template></el-table-column>
              <el-table-column label="计分说明" prop="note" min-width="190" />
            </el-table>
            <h4>② 这份答卷如何换算成百分制</h4>
            <dl class="sheet-equations"><dt>实得分相加</dt><dd>{{ formatFormulaPreview(sheet.earnedFormula) }}</dd><dt>满分相加</dt><dd>{{ formatFormulaPreview(sheet.maximumFormula) }}</dd><dt>换算百分制</dt><dd>{{ formatFormulaPreview(sheet.formula) }} ≈ <strong>{{ sheet.result ?? '数据不足' }}</strong></dd></dl><details><summary>完整精度</summary><div class="formula">实得分：{{ sheet.earnedFormula }}</div><div class="formula">满分：{{ sheet.maximumFormula }}</div><div class="formula">换算：{{ sheet.formula }}</div><div class="formula">未舍入结果：{{ sheet.exactResult }}</div></details>
          </article>
          <article v-if="relationSummary" class="sheet-card relation-summary"><h3>③ {{ selection.label }}的最终来源：对已提交答卷取平均</h3><div class="formula">{{ formatFormulaPreview(relationSummary.formula) }} ≈ <strong>{{ relationSummary.result ?? '数据不足' }}</strong></div><details><summary>完整精度</summary><div class="formula">{{ relationSummary.formula }}</div><div class="formula">未舍入结果：{{ relationSummary.exactResult }}</div></details><p>{{ formatFormulaPreview(relationSummary.note) }}</p><p>只有一份有效答卷时，关系得分就是这份答卷的百分制得分。除法和平均可能产生小数，最终展示两位。</p></article>
        </div>
      </template>
    </template>
  </section>
</template>

<style scoped>
.source-panel { display: grid; gap: 18px; }
h2, h3, p { margin: 0; }
p, small { font-size: 13px; line-height: 1.7; color: var(--fb-text-muted, #64748b); }
small { display: block; margin-top: 7px; }
.formula { white-space: normal; overflow-wrap: anywhere; line-height: 1.8; font-variant-numeric: tabular-nums; }
.formula-table :deep(.el-button + .el-button) { margin-left: 0; }
.sheet-breakdown { display: grid; gap: 18px; }
.sheet-card { border: 1px solid var(--el-border-color); border-radius: 10px; padding: 18px; min-width: 0; }
.sheet-card h4 { margin: 18px 0 12px; }
.sheet-equations { display: grid; grid-template-columns: 110px minmax(0, 1fr); gap: 12px; line-height: 1.8; }
.sheet-equations dd { margin: 0; overflow-wrap: anywhere; font-variant-numeric: tabular-nums; }
.relation-summary { background: var(--el-fill-color-light); }
.relation-summary .formula { margin: 14px 0; }
summary { cursor: pointer; color: var(--el-color-primary); font-size: 13px; margin: 10px 0; }
</style>
