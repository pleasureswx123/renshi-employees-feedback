<script setup>
import { ElMessage } from 'element-plus'
import { defineAsyncComponent, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import ScoreSourcePanel from '@/components/feedback/reports/ScoreSourcePanel.vue'
import IndicatorComparison from '@/components/feedback/reports/IndicatorComparison.vue'
import PersonalReportPanel from '@/components/feedback/reports/PersonalReportPanel.vue'
import WorkspaceIcon from '@/components/WorkspaceIcon.vue'
import { usePermissionStore } from '@/stores/permission'
import { useProjectReportsStore } from '@/stores/projectReports'

const ReportScoreChart = defineAsyncComponent(() => import('@/components/feedback/reports/ReportScoreChart.vue'))
const route = useRoute()
const store = useProjectReportsStore()
const permissions = usePermissionStore()
const filters = reactive({ keyword: '', department: '', sortRelationId: 'total', sortOrder: 'desc', pageNum: 1, pageSize: 20 })
const selectedIndicator = ref('all')
let lastPageSize = 20
const form = ref()
const personVisible = ref(false)
const sourceVisible = ref(false)
const sourceTarget = ref(null)
function showSource(target) { sourceTarget.value = target; sourceVisible.value = true }
const reportTab = ref('ranking')
const rulesVisible = ref(false)
const scorePercent = value => Math.max(0, Math.min(100, Number(value) || 0))
let active = true
const scoreText = value => value ?? '数据不足'
async function load() {
  if (store.loading.generate && store.projectId === Number(route.params.projectId)) return
  personVisible.value = false
  sourceVisible.value = false
  const projectId = Number(route.params.projectId)
  const report = await store.loadTeam(projectId, { ...filters, department: filters.department || undefined, sortRelationId: filters.sortRelationId === 'total' ? undefined : filters.sortRelationId })
  if (active && Number(route.params.projectId) === projectId && store.projectId === projectId &&
      report && !report.ready && !store.errors.generate && permissions.hasPermission('feedback:report:view')) {
    await generate()
  }
}
async function search() {
  if (store.loading.team || store.loading.generate) return
  const projectId = route.params.projectId
  if (!await form.value.validate().catch(() => false)) return
  if (!active || projectId !== route.params.projectId) return
  filters.pageNum = 1
  await load()
}
async function generate() {
  const result = await store.generate()
  if (result) { filters.pageNum = 1; filters.keyword = ''; ElMessage.success('报告已生成') }
}
async function showPerson(row) {
  personVisible.value = true
  await store.loadPerson(row.targetUserId)
}
function paginationChanged(pageNum, pageSize) { filters.pageNum = pageSize === lastPageSize ? pageNum : 1; filters.pageSize = pageSize; lastPageSize = pageSize; load() }
watch(() => route.params.projectId, () => { Object.assign(filters, { keyword: '', department: '', sortRelationId: 'total', sortOrder: 'desc', pageNum: 1 }); selectedIndicator.value = 'all'; reportTab.value = 'ranking'; rulesVisible.value = false; load() }, { immediate: true })
onBeforeUnmount(() => { active = false; store.reset() })
</script>

<template>
  <section class="reports-page">
    <nav class="report-navigation"><el-button @click="$router.push('/hr/reports')">← 返回报告列表</el-button></nav>
    <header class="report-header">
      <div class="report-heading-group"><div class="report-heading-icon"><WorkspaceIcon name="report" /></div><div><h1 class="page-heading">{{ store.team?.projectName || '评价报告' }}</h1><p class="page-description">按最终得分查看团队排名，点击得分详情了解指标表现与计分依据。</p></div></div>
      <div class="actions">
        <el-button v-if="permissions.hasPermission('feedback:answer:view')" @click="$router.push(`/hr/projects/${route.params.projectId}/answers`)">已提交答卷</el-button>
        <el-button :loading="store.loading.team" :disabled="store.loading.team || store.loading.generate" @click="load">刷新</el-button>
      </div>
    </header>
    <el-alert v-if="store.errors.team || store.errors.generate" :title="store.errors.team || store.errors.generate" type="error" :closable="false" show-icon />
    <div v-if="store.loading.team || store.loading.generate" role="status">
      <p v-if="store.loading.generate" class="page-description">正在生成报告，请稍候…</p>
      <el-skeleton :rows="7" animated />
    </div>
    <template v-else-if="store.team">
      <el-alert v-if="!store.team.dataScopeComplete" :title="store.team.scopeMessage" type="warning" :closable="false" show-icon />
      <div class="summary">
        <el-card shadow="never"><span class="summary-label">被评价人</span><div class="summary-value">{{ store.team.targetCount }}<small>人</small></div></el-card>
        <el-card shadow="never"><span class="summary-label">已提交 / 应完成</span><div class="summary-value">{{ store.team.submittedCount }}<span class="summary-secondary"> / {{ store.team.expectedCount }}</span><small>份</small></div></el-card>
        <el-card shadow="never"><span class="summary-label">完成率</span><div class="summary-value">{{ store.team.completionRate }}<small>%</small></div></el-card>
      </div>
      <el-card v-if="!store.team.ready" shadow="never">
        <el-empty description="报告暂未生成"><el-button type="primary" :loading="store.loading.generate" :disabled="store.loading.generate" @click="generate">重试生成报告</el-button></el-empty>
        <p class="page-description">生成当前可见人员的报告，并保存本次计算依据。未提交任务不会按零分计入。</p>
      </el-card>
      <el-card v-else shadow="never" class="team-report-card">
        <div class="report-section-heading"><h2>团队排名与明细</h2><el-button link type="primary" @click="rulesVisible = true">计分说明</el-button></div>
        <el-tabs v-model="reportTab" aria-label="报告视图"><el-tab-pane label="团队排名" name="ranking" /><el-tab-pane label="指标对比" name="indicators" /><el-tab-pane label="得分图表" name="charts" /></el-tabs>
        <div class="score-guide"><strong>排名看最终得分</strong><p>最终得分由他人的评价按发布时的关系、指标权重计算，不与自评取平均。自评通常仅供对照；标注“仅自评”的人员，以自评计入最终得分。</p></div>
        <el-form ref="form" :model="filters" inline size="small" class="workspace-filter report-filters">
          <el-form-item label="被评价人" prop="keyword" :rules="[{ max: 200, message: '最多200字' }]">
            <el-input v-model="filters.keyword" maxlength="200" clearable @keyup.enter="search" />
          </el-form-item>
          <el-form-item v-if="reportTab === 'indicators'" label="查看维度"><el-select v-model="selectedIndicator" aria-label="查看维度" style="width: 145px"><el-option label="全部指标" value="all" /><el-option v-for="item in store.team.indicatorOptions || []" :key="item.indicatorId" :label="item.indicatorName" :value="item.indicatorId" /></el-select></el-form-item>
          <el-form-item label="部门"><el-select v-model="filters.department" aria-label="部门" clearable filterable placeholder="全部部门" style="width: 145px"><el-option v-for="name in store.team.departmentOptions || []" :key="name" :label="name" :value="name" /></el-select></el-form-item>
          <el-form-item label="排序"><el-select v-model="filters.sortRelationId" aria-label="排序字段" style="width: 100px"><el-option label="总得分" value="total" /><el-option v-for="item in store.team.relationOptions || []" :key="item.relationId" :label="item.relationType === 'SELF' ? '自己' : item.relationName" :value="item.relationId" /></el-select></el-form-item>
          <el-form-item><el-select v-model="filters.sortOrder" aria-label="排序方向" style="width: 105px"><el-option label="高到低" value="desc" /><el-option label="低到高" value="asc" /></el-select></el-form-item>
          <el-form-item><el-button type="primary" :disabled="store.loading.team" @click="search">查询</el-button></el-form-item>
        </el-form>
        <IndicatorComparison v-if="reportTab === 'indicators'" :rows="store.team.rows" :selected-indicator="selectedIndicator" :show-toolbar="false" @detail="showPerson" @source="showSource" />
        <ReportScoreChart v-else-if="reportTab === 'charts'" :rows="store.team.rows" @source="showSource" />
        <el-table v-else :data="store.team.rows" empty-text="没有匹配的被评价人" class="report-table">
          <el-table-column label="排名" width="70"><template #default="{ row }"><span class="rank-label">{{ row.rank ?? '—' }}</span></template></el-table-column>
          <el-table-column prop="targetName" label="被评价人 / 部门" min-width="180"><template #default="{ row }"><strong class="report-person">{{ row.targetName }}</strong><span class="report-dept">{{ row.targetDeptName }}</span></template></el-table-column>
          <el-table-column label="最终得分" min-width="230"><template #default="{ row }"><el-button link :class="{ 'primary-score': row.score != null }" @click="showSource({ row, key: 'total' })">{{ row.score ?? (row.onlySelfEvaluation ? '自评数据不足' : '他评数据不足') }}</el-button><el-progress v-if="row.score != null" :percentage="scorePercent(row.score)" :show-text="false" :stroke-width="7" :aria-label="`最终得分 ${row.score}，满分100`" class="score-bar" /><span class="report-dept">{{ row.onlySelfEvaluation ? '仅自评 · 以自评计分' : '按他评加权计分' }}</span></template></el-table-column>
          <el-table-column label="自评参考分" min-width="150"><template #default="{ row }">{{ scoreText(row.selfScore) }}<span class="report-dept">{{ row.onlySelfEvaluation ? '本人的自评用于最终得分' : '仅供对照，不计入最终得分' }}</span></template></el-table-column>
          <el-table-column label="完成情况" min-width="135"><template #default="{ row }">{{ row.submittedCount }}/{{ row.expectedCount }}（{{ row.completionRate }}%）<div v-if="row.hasMissingData"><el-tag type="warning" size="small">存在缺失数据</el-tag></div></template></el-table-column>
          <el-table-column label="操作" width="145" fixed="right"><template #default="{ row }"><el-button link type="primary" @click="showPerson(row)">查看得分详情</el-button></template></el-table-column>
        </el-table>
        <p class="page-description">得分为百分制。同分并列，排名按未舍入的最终得分计算；数据不足者不参与排名，未提交任务不按零分计入。</p>
        <el-pagination layout="total, sizes, prev, pager, next" :page-sizes="[10, 20, 30, 50, 100]" :total="store.team.total" v-model:current-page="filters.pageNum" v-model:page-size="filters.pageSize" @change="paginationChanged" />
      </el-card>
    </template>
    <el-drawer v-model="sourceVisible" title="得分来源" size="min(1150px, 96vw)" destroy-on-close><ScoreSourcePanel v-if="sourceVisible && sourceTarget" :target="sourceTarget" /></el-drawer>
    <el-dialog v-model="rulesVisible" title="计分说明" width="min(700px, 94vw)">
      <div class="rules-content"><p>以下口径来自项目发布时冻结的计分配置，报告中仅供查阅。</p><ol><li>每份答卷先将指标对应题目的得分换算为百分制。</li><li>同一评价关系内多人取平均，再按有效关系权重合成指标得分。</li><li>各指标得分按指标权重加权，得到用于排名的最终得分。</li></ol><p>自评通常仅作对照；发布时仅配置自评的人员，以自评计分。未提交任务不按零分计入，缺失关系的权重在有效计分关系中重新分配。</p>
      <el-table :data="store.team?.rows?.[0]?.indicators || []" empty-text="当前筛选结果为空，请清除筛选后查看配置"><el-table-column prop="indicatorName" label="冻结指标" /><el-table-column prop="weight" label="指标权重（%）" width="150" /></el-table>
      <p>各关系的原始权重和实际权重可在“查看得分详情”中核对；“指标对比”支持查看同一指标的各关系得分。</p></div>
    </el-dialog>
    <el-drawer v-model="personVisible" title="得分详情" size="min(1100px, 96vw)" destroy-on-close @close="store.clear('person')">
      <el-skeleton v-if="store.loading.person" :rows="8" animated />
      <el-alert v-else-if="store.errors.person" :title="store.errors.person" type="error" :closable="false" />
      <PersonalReportPanel v-else-if="store.person" :report="store.person" />
    </el-drawer>
  </section>
</template>

<style scoped>
.report-filters { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; }
.report-filters :deep(.el-form-item) { margin: 0; }
.report-filters :deep(.el-input) { width: 145px; }
.reports-page { display: grid; gap: 24px; min-width: 0; max-width: 1440px; margin: auto; padding-top: 12px; }
.report-navigation .el-button { border-radius: 8px; }
.report-header { display: flex; gap: 20px; justify-content: space-between; align-items: flex-start; }
.report-header > div:first-child { min-width: 0; }
.report-heading-group { display: flex; gap: 16px; align-items: center; }
.report-heading-icon { display: grid; place-items: center; flex: none; width: 52px; height: 52px; border-radius: 16px; background: var(--el-color-primary-light-9); color: var(--el-color-primary); font-size: 26px; }
.page-heading { margin: 0 0 8px; font-size: 26px; overflow-wrap: anywhere; }
.report-header .page-description { margin: 0; line-height: 1.7; }
.actions { display: flex; gap: 16px; align-items: center; }
.actions { flex-shrink: 0; }
.summary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 18px; }
.reports-page:deep(.el-card) { border-radius: 12px; }
.summary-label { color: var(--fb-text-muted, #64748b); font-size: 13px; }
.summary-value { margin-top: 12px; font-size: 28px; font-weight: 600; font-variant-numeric: tabular-nums; }
.summary-value small { margin-left: 8px; font-size: 14px; font-weight: 400; color: var(--fb-text-muted, #64748b); }
.summary-secondary { font-size: 20px; color: var(--fb-text-muted, #64748b); }
.team-report-card:deep(.el-card__body) { padding: 24px; }
.report-table:deep(.el-table__cell) { padding-block: 18px; }
.report-table { font-variant-numeric: tabular-nums; }
.rank-label { display: inline-grid; place-items: center; min-width: 28px; height: 28px; border-radius: 8px; background: var(--el-fill-color-light); font-weight: 600; }
.report-person { display: block; font-weight: 600; }
.report-dept { display: block; margin-top: 6px; color: var(--fb-text-muted, #64748b); font-size: 12px; overflow-wrap: anywhere; }
.score-guide { padding: 14px 16px; margin-bottom: 20px; border-radius: 8px; background: var(--el-fill-color-light); font-size: 13px; line-height: 1.7; }
.score-guide p { margin: 4px 0 0; color: var(--fb-text-muted, #64748b); }
.score-bar { max-width: 240px; margin-top: 10px; }
.report-section-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; }
.rules-content { line-height: 1.8; }
.rules-content p:first-child { margin-top: 0; }
.primary-score { color: var(--el-color-primary); font-size: 21px; font-weight: 600; }
h2 { font-size: 18px; margin: 0 0 20px; }
@media (max-width: 700px) {
  .reports-page { gap: 18px; padding-top: 0; }
  .report-header { flex-direction: column; }
  .report-heading-group { align-items: flex-start; gap: 12px; }
  .page-heading { font-size: 23px; }
  .summary { grid-template-columns: minmax(0, 1fr); gap: 12px; }
  .summary :deep(.el-card__body) { display: flex; justify-content: space-between; align-items: center; }
  .summary-value { margin-top: 0; font-size: 24px; }
  .team-report-card:deep(.el-card__body) { padding: 18px; }
}
</style>
