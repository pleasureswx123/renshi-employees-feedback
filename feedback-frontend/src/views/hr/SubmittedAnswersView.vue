<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import QuestionRenderer from '@/components/feedback/questions/QuestionRenderer.vue'
import { usePermissionStore } from '@/stores/permission'
import { useProjectReportsStore } from '@/stores/projectReports'
import { restoreAnswers } from '@/utils/answerSheet'
import { listAnswerProjects } from '@/api/feedback/reports'
import WorkspaceIcon from '@/components/WorkspaceIcon.vue'
import { formatDateTime, formatTableDate, trimDecimalZeros } from '@/utils/displayFormat'

const route = useRoute()
const router = useRouter()
const store = useProjectReportsStore()
const permissions = usePermissionStore()
const form = ref()
const filters = reactive({ projectId: null, keyword: '', pageNum: 1, pageSize: 20 })
const opening = ref(false)
const detailVisible = ref(false)
const projectOptions = ref([])
const selectedProject = ref(null)
const projectsLoading = ref(false)
const projectsError = ref('')
let projectEpoch = 0
async function findProjects(keyword = '') {
  const epoch = ++projectEpoch
  projectsLoading.value = true
  projectsError.value = ''
  try {
    const response = await listAnswerProjects({ keyword, pageNum: 1, pageSize: 100 })
    if (active && epoch === projectEpoch) projectOptions.value = response.rows || []
  } catch (error) { if (active && epoch === projectEpoch) { projectOptions.value = []; projectsError.value = error.message || '项目加载失败，请重试' } }
  finally { if (active && epoch === projectEpoch) projectsLoading.value = false }
}
async function resolveProject(id) {
  try {
    const response = await listAnswerProjects({ projectId: id, pageNum: 1, pageSize: 1 })
    if (active && Number(route.params.projectId) === id) selectedProject.value = response.rows?.[0] || null
  } catch { /* 答卷接口会独立反馈项目权限或读取错误。 */ }
}
const options = computed(() => [...new Map([...(selectedProject.value ? [selectedProject.value] : []), ...projectOptions.value].map(item => [item.projectId, item])).values()])
let active = true
const values = computed(() => store.answer ? restoreAnswers(store.answer) : {})
const rules = { projectId: [{ validator: (_rule, value, done) => done(Number.isSafeInteger(value) && value > 0 ? undefined : new Error('请选择评价项目')), trigger: 'change' }] }
async function search() {
  if (opening.value || store.loading.answers) return
  opening.value = true
  try {
    const id = filters.projectId
    if (!await form.value.validate().catch(() => false)) return
    if (!active || id !== filters.projectId) return
    filters.pageNum = 1
    if (Number(route.params.projectId) !== id) await router.push(`/hr/projects/${id}/answers`)
    else await load()
  } finally { opening.value = false }
}
async function load() {
  detailVisible.value = false
  await store.loadAnswers(Number(route.params.projectId), { keyword: filters.keyword, pageNum: filters.pageNum, pageSize: filters.pageSize })
}
function pageChanged(pageNum) { filters.pageNum = pageNum; load() }
async function showAnswer(row) { detailVisible.value = true; await store.loadAnswer(row.assignmentId) }
watch(() => route.params.projectId, id => {
  store.reset()
  filters.projectId = id ? Number(id) : null
  filters.keyword = ''
  filters.pageNum = 1
  detailVisible.value = false
  selectedProject.value = null
  if (id) { resolveProject(Number(id)); load() }
}, { immediate: true })
findProjects()
onBeforeUnmount(() => { active = false; store.reset() })
</script>

<template>
  <section class="submitted-answers">
    <header class="answers-header"><div class="answers-heading"><div class="answers-icon"><WorkspaceIcon name="answers" /></div><div>
      <el-button v-if="selectedProject?.status === 'COMPLETED' && permissions.hasPermission('feedback:report:view')" link type="primary" @click="$router.push(`/hr/projects/${route.params.projectId}/reports`)">查看项目报告</el-button>
      <h1 class="page-heading">已提交答卷</h1>
      <p class="page-description">查看谁评价了谁，以及实际提交的选项、打分和文字回答。答卷提交后只读，可用于核对评价记录。</p>
    </div></div></header>
    <el-card shadow="never" class="answer-list-card">
      <el-form ref="form" :model="filters" :rules="rules" inline class="workspace-filter">
        <el-form-item label="评价项目" prop="projectId"><el-select v-model="filters.projectId" filterable remote :remote-method="findProjects" :loading="projectsLoading" placeholder="输入项目名称搜索" style="width: 300px"><el-option v-for="item in options" :key="item.projectId" :value="item.projectId" :label="item.projectName"><span>{{ item.projectName }}</span><small class="project-status">{{ item.status === 'COMPLETED' ? '已完成' : '进行阶段' }}</small></el-option></el-select></el-form-item>
        <el-form-item label="被评价人" prop="keyword"><el-input v-model="filters.keyword" maxlength="200" placeholder="输入被评价人姓名" clearable @keyup.enter="search" /></el-form-item>
        <el-form-item><el-button type="primary" :loading="opening || store.loading.answers" :disabled="opening || store.loading.answers" @click="search">查询</el-button></el-form-item>
      </el-form>
      <el-alert v-if="projectsError" :title="projectsError" type="error" :closable="false"><el-button link @click="findProjects()">重试加载项目</el-button></el-alert>
      <div class="answer-list-heading"><h2>{{ selectedProject?.projectName || '答卷记录' }}</h2><span>仅展示已提交记录 · 查看操作留存审计</span></div>
      <el-alert v-if="store.errors.answers" :title="store.errors.answers" type="error" :closable="false" />
      <el-empty v-if="!route.params.projectId" description="请先按名称选择评价项目，再点击查询查看答卷" />
      <el-table v-else v-loading="store.loading.answers" :data="store.answers?.rows || []" empty-text="暂无可查看的已提交答卷">
        <el-table-column prop="targetName" label="被评价人" min-width="140" />
        <el-table-column prop="targetDeptName" label="被评价人部门" min-width="140" />
        <el-table-column prop="evaluatorName" label="评价人" min-width="130" />
        <el-table-column label="答卷原始总分" width="150"><template #header><el-tooltip content="本份答卷各计分题得分之和，非百分制，未按指标或评价关系加权。" placement="top"><span>答卷原始总分 ⓘ</span></el-tooltip></template><template #default="{ row }"><strong class="answer-score">{{ row.rawTotalScore == null ? '暂无分数' : trimDecimalZeros(row.rawTotalScore) }}</strong></template></el-table-column>
        <el-table-column prop="relationName" label="关系" width="100" />
        <el-table-column prop="submittedTime" label="提交时间" min-width="180" :formatter="formatTableDate" />
        <el-table-column label="操作" width="110"><template #default="{ row }"><el-button link type="primary" @click="showAnswer(row)">查看答卷</el-button></template></el-table-column>
      </el-table>
      <el-pagination v-if="route.params.projectId" layout="total, prev, pager, next" :total="store.answers?.total || 0" :current-page="filters.pageNum" :page-size="filters.pageSize" @current-change="pageChanged" />
    </el-card>
    <el-drawer v-model="detailVisible" title="已提交答卷" size="min(880px, 96vw)" destroy-on-close @close="store.clear('answer')">
      <el-skeleton v-if="store.loading.answer" :rows="8" animated />
      <el-alert v-else-if="store.errors.answer" :title="store.errors.answer" type="error" :closable="false" />
      <template v-else-if="store.answer">
        <h2>{{ store.answer.evaluatorName }} → {{ store.answer.targetName }}</h2>
        <p>答卷原始总分：{{ store.answer.rawTotalScore == null ? '暂无分数' : trimDecimalZeros(store.answer.rawTotalScore) }}（各计分题得分之和，未加权）</p>
        <p>{{ store.answer.relationName }} · {{ formatDateTime(store.answer.submittedTime) }} · 已提交，只读</p>
        <section v-for="page in store.answer.questionnaire.pages" :key="page.pageId">
          <h3>{{ page.pageTitle }}</h3>
          <div v-for="question in page.questions" :key="question.questionId" class="answer-question">
            <QuestionRenderer :question="question" mode="readonly" :model-value="values[question.questionCode]" />
          </div>
        </section>
      </template>
    </el-drawer>
  </section>
</template>

<style scoped>
.submitted-answers { display: grid; gap: 24px; min-width: 0; max-width: 1440px; margin: auto; padding-top: 12px; }
.answers-heading { display: flex; gap: 16px; align-items: center; }
.answers-icon { background: var(--el-color-primary-light-9); color: var(--el-color-primary); padding: 14px; border-radius: 14px; font-size: 26px; display: grid; }
.page-heading { margin: 0 0 10px; font-size: 26px; }
.page-description { margin: 0; line-height: 1.8; }
.answer-list-card { border-radius: 12px; }
.answer-list-card :deep(.el-card__body) { padding: 24px; }
.answer-list-card :deep(.el-table__cell) { padding-block: 16px; }
.answer-list-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin: 20px 0; }
.answer-list-heading h2 { margin: 0; font-size: 18px; }
.answer-list-heading span, .project-status { color: var(--fb-text-muted, #64748b); font-size: 12px; }
.answer-score { color: var(--el-color-primary); font-variant-numeric: tabular-nums; }
.project-status { margin-left: 16px; }
@media (max-width: 600px) { .answers-heading { align-items: flex-start; } .answer-list-card :deep(.el-card__body) { padding: 16px; } }
.el-pagination { margin-top: 20px; }
.answer-question { padding: 18px 0; border-bottom: 1px solid var(--fb-border, #ebeef5); overflow-wrap: anywhere; }
h2, h3, p { overflow-wrap: anywhere; }
</style>
