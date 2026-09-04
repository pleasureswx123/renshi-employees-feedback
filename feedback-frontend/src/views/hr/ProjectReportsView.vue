<script setup>
import { ElMessage } from 'element-plus'
import { onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import PersonalReportPanel from '@/components/feedback/reports/PersonalReportPanel.vue'
import { usePermissionStore } from '@/stores/permission'
import { useProjectReportsStore } from '@/stores/projectReports'

const route = useRoute()
const store = useProjectReportsStore()
const permissions = usePermissionStore()
const filters = reactive({ keyword: '', pageNum: 1, pageSize: 20 })
const form = ref()
const personVisible = ref(false)
let active = true
const scoreText = value => value ?? '数据不足'
async function load() {
  personVisible.value = false
  await store.loadTeam(Number(route.params.projectId), { ...filters })
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
function pageChanged(pageNum) { filters.pageNum = pageNum; load() }
watch(() => route.params.projectId, () => { filters.keyword = ''; filters.pageNum = 1; load() }, { immediate: true })
onBeforeUnmount(() => { active = false; store.reset() })
</script>

<template>
  <section class="reports-page">
    <header class="report-header workspace-page-header">
      <div><el-button link type="primary" @click="$router.push('/hr/reports')">返回报告列表</el-button><h1 class="page-heading">{{ store.team?.projectName || '评价报告' }}</h1><p class="page-description">综合分按发布时的指标与关系权重计算。自评仅作对照，发布时仅配置自评的人员除外。</p></div>
      <div class="actions">
        <el-button v-if="permissions.hasPermission('feedback:answer:view')" @click="$router.push(`/hr/projects/${route.params.projectId}/answers`)">原始答案</el-button>
        <el-button :loading="store.loading.team" :disabled="store.loading.team || store.loading.generate" @click="load">刷新</el-button>
      </div>
    </header>
    <el-alert v-if="store.errors.team || store.errors.generate" :title="store.errors.team || store.errors.generate" type="error" :closable="false" show-icon />
    <el-skeleton v-if="store.loading.team" :rows="7" animated />
    <template v-else-if="store.team">
      <el-alert v-if="!store.team.dataScopeComplete" :title="store.team.scopeMessage" type="warning" :closable="false" show-icon />
      <el-card shadow="never"><div class="summary"><span>被评价人 <strong>{{ store.team.targetCount }}</strong></span><span>已提交 <strong>{{ store.team.submittedCount }} / {{ store.team.expectedCount }}</strong> 份</span><span>完成率 <strong>{{ store.team.completionRate }}%</strong></span></div></el-card>
      <el-card v-if="!store.team.ready" shadow="never">
        <el-empty description="报告尚未生成"><el-button type="primary" :loading="store.loading.generate" :disabled="store.loading.generate" @click="generate">生成报告</el-button></el-empty>
        <p class="page-description">生成当前可见人员的报告，并保存本次计算依据。未提交任务不会按零分计入。</p>
      </el-card>
      <el-card v-else shadow="never">
        <h2>团队排名与明细</h2>
        <el-form ref="form" :model="filters" inline class="workspace-filter">
          <el-form-item label="被评价人" prop="keyword" :rules="[{ max: 200, message: '最多200字' }]">
            <el-input v-model="filters.keyword" maxlength="200" clearable @keyup.enter="search" />
          </el-form-item>
          <el-form-item><el-button type="primary" :disabled="store.loading.team" @click="search">查询</el-button></el-form-item>
        </el-form>
        <el-table :data="store.team.rows" border empty-text="没有匹配的被评价人">
          <el-table-column label="排名" width="70"><template #default="{ row }">{{ row.rank ?? '—' }}</template></el-table-column>
          <el-table-column prop="targetName" label="被评价人" min-width="150" />
          <el-table-column prop="targetDeptName" label="部门" min-width="130" />
          <el-table-column v-for="col in [{ key: 'score', label: '综合分' }, { key: 'selfScore', label: '自评分' }, { key: 'otherScore', label: '他评分' }]" :key="col.key" :label="col.label" width="105"><template #default="{ row }">{{ scoreText(row[col.key]) }}</template></el-table-column>
          <el-table-column label="指标分" min-width="190"><template #default="{ row }"><div v-for="item in row.indicators" :key="item.indicatorId">{{ item.indicatorName }}：{{ scoreText(item.score) }}</div></template></el-table-column>
          <el-table-column label="完成情况" min-width="135"><template #default="{ row }">{{ row.submittedCount }}/{{ row.expectedCount }}（{{ row.completionRate }}%）<div v-if="row.hasMissingData"><el-tag type="warning" size="small">存在缺失数据</el-tag></div><div v-if="row.onlySelfEvaluation">仅自评</div></template></el-table-column>
          <el-table-column label="操作" width="120" fixed="right"><template #default="{ row }"><el-button link type="primary" @click="showPerson(row)">个人报告</el-button></template></el-table-column>
        </el-table>
        <p class="page-description">同分并列；分数显示两位小数，排名按未舍入得分计算。数据不足者不参与排名。</p>
        <el-pagination layout="total, prev, pager, next" :total="store.team.total" :current-page="filters.pageNum" :page-size="filters.pageSize" @current-change="pageChanged" />
      </el-card>
    </template>
    <el-drawer v-model="personVisible" title="个人报告" size="min(1100px, 96vw)" destroy-on-close @close="store.clear('person')">
      <el-skeleton v-if="store.loading.person" :rows="8" animated />
      <el-alert v-else-if="store.errors.person" :title="store.errors.person" type="error" :closable="false" />
      <PersonalReportPanel v-else-if="store.person" :report="store.person" />
    </el-drawer>
  </section>
</template>

<style scoped>
.reports-page { display: grid; gap: 20px; min-width: 0; }
.report-header { display: flex; gap: 20px; justify-content: space-between; align-items: flex-start; }
.report-header > div:first-child { min-width: 0; }
.page-heading { margin-top: 8px; overflow-wrap: anywhere; }
.actions, .summary { display: flex; gap: 16px; align-items: center; }
.actions { flex-shrink: 0; }
.summary { flex-wrap: wrap; }
.summary strong { font-size: 22px; margin-left: 8px; }
h2 { font-size: 18px; margin: 0 0 20px; }
@media (max-width: 700px) { .report-header { flex-direction: column; } }
</style>
