<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import QuestionRenderer from '@/components/feedback/questions/QuestionRenderer.vue'
import { usePermissionStore } from '@/stores/permission'
import { useProjectReportsStore } from '@/stores/projectReports'
import { restoreAnswers } from '@/utils/answerSheet'
import { formatTableDate } from '@/utils/displayFormat'

const route = useRoute()
const router = useRouter()
const store = useProjectReportsStore()
const permissions = usePermissionStore()
const form = ref()
const filters = reactive({ projectId: null, keyword: '', pageNum: 1, pageSize: 20 })
const opening = ref(false)
const detailVisible = ref(false)
let active = true
const values = computed(() => store.answer ? restoreAnswers(store.answer) : {})
const rules = { projectId: [{ validator: (_rule, value, done) => done(Number.isSafeInteger(value) && value > 0 ? undefined : new Error('请输入有效项目ID')), trigger: 'change' }] }
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
  if (id) load()
}, { immediate: true })
onBeforeUnmount(() => { active = false; store.reset() })
</script>

<template>
  <section class="submitted-answers">
    <header class="workspace-page-header"><div>
      <el-button v-if="route.params.projectId && permissions.hasPermission('feedback:report:view')" link type="primary" @click="$router.push(`/hr/projects/${route.params.projectId}/reports`)">查看项目报告</el-button>
      <h1 class="page-heading">已提交原始答案</h1>
      <p class="page-description">仅显示当前数据范围内的已提交答卷，包含评价人身份。查看记录会留存审计。</p>
    </div></header>
    <el-card shadow="never">
      <el-form ref="form" :model="filters" :rules="rules" inline class="workspace-filter">
        <el-form-item label="项目ID" prop="projectId"><el-input-number v-model="filters.projectId" :min="1" :precision="0" :controls="false" @keyup.enter="search" /></el-form-item>
        <el-form-item label="被评价人" prop="keyword"><el-input v-model="filters.keyword" maxlength="200" clearable @keyup.enter="search" /></el-form-item>
        <el-form-item><el-button type="primary" :loading="opening || store.loading.answers" :disabled="opening || store.loading.answers" @click="search">查询</el-button></el-form-item>
      </el-form>
      <el-alert v-if="store.errors.answers" :title="store.errors.answers" type="error" :closable="false" />
      <el-table v-loading="store.loading.answers" :data="store.answers?.rows || []" empty-text="暂无可查看的已提交答卷">
        <el-table-column prop="targetName" label="被评价人" min-width="140" />
        <el-table-column prop="targetDeptName" label="被评价人部门" min-width="140" />
        <el-table-column prop="evaluatorName" label="评价人" min-width="130" />
        <el-table-column prop="relationName" label="关系" width="100" />
        <el-table-column prop="submittedTime" label="提交时间" min-width="180" :formatter="formatTableDate" />
        <el-table-column label="操作" width="110"><template #default="{ row }"><el-button link type="primary" @click="showAnswer(row)">查看答案</el-button></template></el-table-column>
      </el-table>
      <el-pagination layout="total, prev, pager, next" :total="store.answers?.total || 0" :current-page="filters.pageNum" :page-size="filters.pageSize" @current-change="pageChanged" />
    </el-card>
    <el-drawer v-model="detailVisible" title="已提交原始答案" size="min(880px, 96vw)" destroy-on-close @close="store.clear('answer')">
      <el-skeleton v-if="store.loading.answer" :rows="8" animated />
      <el-alert v-else-if="store.errors.answer" :title="store.errors.answer" type="error" :closable="false" />
      <template v-else-if="store.answer">
        <h2>{{ store.answer.evaluatorName }} → {{ store.answer.targetName }}</h2>
        <p>{{ store.answer.relationName }} · {{ store.answer.submittedTime }} · 已提交，只读</p>
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
.submitted-answers { display: grid; gap: 20px; min-width: 0; }
.el-pagination { margin-top: 20px; }
.answer-question { padding: 18px 0; border-bottom: 1px solid #ebeef5; overflow-wrap: anywhere; }
h2, h3, p { overflow-wrap: anywhere; }
</style>
