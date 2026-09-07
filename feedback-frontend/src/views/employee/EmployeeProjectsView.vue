<script setup>
import { onMounted, onBeforeUnmount, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { listMyProjects } from '@/api/feedback/tasks'
import { formatDateTime } from '@/utils/displayFormat'
import WorkspaceIcon from '@/components/WorkspaceIcon.vue'

const router = useRouter()
const form = ref()
const filters = reactive({ keyword: '' })
const pageNum = ref(1)
const rows = ref([])
const total = ref(0)
const loading = ref(false)
const error = ref('')
let requestId = 0

async function load(page = pageNum.value) {
  const id = ++requestId
  pageNum.value = page
  loading.value = true
  error.value = ''
  try {
    const response = await listMyProjects({ pageNum: page, pageSize: 12, keyword: filters.keyword.trim() })
    if (id !== requestId) return
    rows.value = response.rows
    total.value = response.total
  } catch (failure) {
    if (id === requestId) { error.value = failure.message; rows.value = [] }
  } finally {
    if (id === requestId) loading.value = false
  }
}

async function search() {
  if (loading.value || !await form.value.validate().catch(() => false)) return
  await load(1)
}

onMounted(() => load())
onBeforeUnmount(() => { requestId++ })
</script>

<template>
  <section class="employee-page">
    <header class="todo-heading"><div class="todo-heading-icon"><WorkspaceIcon name="todos" /></div><div>
      <h1 class="page-heading">我的待办</h1>
      <p class="page-description">选择项目，逐人完成评价；未完成的答案可暂存。</p>
    </div></header>
    <el-card shadow="never" class="employee-filter-card">
    <el-form ref="form" :model="filters" inline class="employee-filter workspace-filter" @keydown.enter.prevent="search">
      <el-form-item label="项目名称" prop="keyword" :rules="[{ max: 200, message: '最多输入200字' }]">
        <el-input v-model="filters.keyword" clearable placeholder="搜索项目名称" aria-label="搜索项目名称" />
      </el-form-item>
      <el-form-item><el-button type="primary" :loading="loading" @click="search"><WorkspaceIcon name="search" />查询</el-button></el-form-item>
    </el-form>
    </el-card>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <div v-loading="loading" class="employee-list">
      <el-card v-if="!loading && !error && !rows.length" shadow="never" class="empty-projects">
        <el-empty description="暂无待处理的评价任务" :image-size="110"><p class="page-description">收到参评安排后，评价任务会显示在这里。</p></el-empty>
      </el-card>
      <el-card v-for="project in rows" :key="project.projectId" shadow="never" class="project-card">
        <div class="project-info">
          <div class="project-title"><span class="project-symbol"><WorkspaceIcon name="project" /></span><h2>{{ project.projectName }}</h2></div>
          <p class="project-date">开始时间：{{ formatDateTime(project.publishedTime) }}</p>
        </div>
        <div class="project-progress">
          <div class="progress-caption"><span>评价进度</span><span>已提交 <strong>{{ project.submittedCount }}</strong> / {{ project.totalCount }} 份</span></div>
          <el-progress :percentage="project.totalCount ? Math.round(project.submittedCount / project.totalCount * 100) : 0" :stroke-width="6" :show-text="false" />
          <p class="progress-detail">还需完成 {{ Math.max(0, project.totalCount - project.submittedCount) }} 份<span v-if="project.draftCount"> · 其中 {{ project.draftCount }} 份已暂存</span></p>
        </div>
        <div class="project-footer">
          <el-button type="primary" @click="router.push(`/employee/todos/${project.projectId}`)">{{ project.draftCount || project.submittedCount ? '继续评价' : '开始评价' }}<span class="action-arrow" aria-hidden="true">→</span></el-button>
        </div>
      </el-card>
    </div>
    <el-pagination v-if="total > 12" :current-page="pageNum" :page-size="12" :total="total" layout="prev, pager, next" :disabled="loading" @current-change="load" />
  </section>
</template>

<style scoped>
.employee-page { display: grid; gap: 24px; max-width: 1200px; margin: auto; padding-top: 12px; }
.todo-heading { display: flex; align-items: center; gap: 16px; padding: 8px 0; }
.todo-heading-icon { display: grid; place-items: center; flex: none; width: 52px; height: 52px; border-radius: 16px; background: var(--el-color-primary-light-9); color: var(--el-color-primary); font-size: 26px; }
.todo-heading .page-heading { margin: 0 0 8px; font-size: 26px; }
.todo-heading .page-description { margin: 0; line-height: 1.7; }
.employee-filter-card { border-radius: 12px; }
.employee-filter-card .employee-filter { margin: 0; padding: 0; border: 0; }
.employee-filter-card:deep(.el-form-item) { margin-bottom: 0; }
.employee-list { display: grid; grid-template-columns: minmax(0, 1fr); gap: 16px; min-height: 120px; }
.empty-projects { grid-column: 1 / -1; }
.project-card { border-radius: 14px; }
.project-card:deep(.el-card__body) { display: grid; grid-template-columns: minmax(0, 1fr) minmax(220px, .8fr) auto; align-items: center; gap: 36px; padding: 28px; }
.project-title { display: flex; align-items: center; gap: 12px; }
.project-symbol { display: grid; place-items: center; flex: none; width: 36px; height: 36px; background: var(--el-fill-color-light); color: var(--el-color-primary); border-radius: 10px; font-size: 20px; }
.project-card h2 { margin: 0; font-size: 18px; font-weight: 600; overflow-wrap: anywhere; }
.project-card p, .progress-caption { color: var(--fb-text-muted, #64748b); line-height: 1.6; font-size: 13px; }
.project-date { margin: 12px 0 0; }
.progress-caption { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 10px; }
.progress-caption strong { color: var(--el-text-color-primary); font-size: 17px; font-weight: 600; }
.progress-detail { margin: 10px 0 0; }
.project-footer .el-button { min-height: 40px; border-radius: 8px; padding-inline: 20px; }
.action-arrow { margin-left: 14px; }
@media (max-width: 1100px) { .project-card:deep(.el-card__body) { grid-template-columns: minmax(0, 1fr) auto; gap: 22px; } .project-info { grid-column: 1 / -1; } }
@media (max-width: 760px) {
  .employee-page { gap: 18px; padding-top: 0; }
  .todo-heading { align-items: flex-start; gap: 12px; }
  .todo-heading .page-heading { font-size: 23px; }
  .employee-filter-card:deep(.el-form-item:first-child) { margin-bottom: 14px; }
  .project-card:deep(.el-card__body) { grid-template-columns: minmax(0, 1fr); gap: 20px; padding: 20px; }
  .project-footer .el-button { width: 100%; }
}
</style>
