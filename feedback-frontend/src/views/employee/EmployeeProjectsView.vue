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
    <header class="workspace-page-header"><div>
      <h1 class="page-heading">我的待办</h1>
      <p class="page-description">选择项目，按被评价人分别填写和提交评价。</p>
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
        <h2>{{ project.projectName }}</h2>
        <p>开始时间：{{ formatDateTime(project.publishedTime) }}</p>
        <el-progress :percentage="Math.round(project.submittedCount / project.totalCount * 100)" />
        <div class="project-footer">
          <span>已提交 {{ project.submittedCount }}/{{ project.totalCount }} 份 · 已暂存 {{ project.draftCount }} 份</span>
          <el-button type="primary" @click="router.push(`/employee/todos/${project.projectId}`)">进入项目</el-button>
        </div>
      </el-card>
    </div>
    <el-pagination v-if="total > 12" :current-page="pageNum" :page-size="12" :total="total" layout="prev, pager, next" :disabled="loading" @current-change="load" />
  </section>
</template>

<style scoped>
.employee-page { display: grid; gap: 18px; max-width: 1200px; margin: auto; }
.employee-filter-card .employee-filter { margin: 0; padding: 0; border: 0; }
.employee-filter-card :deep(.el-form-item) { margin-bottom: 0; }
.employee-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; min-height: 120px; }
.empty-projects { grid-column: 1 / -1; }
.project-card h2 { margin: 0; font-size: 17px; font-weight: 600; overflow-wrap: anywhere; }
.project-card p, .project-footer span { color: #64748b; line-height: 1.6; }
.project-footer { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 16px; margin-top: 18px; }
@media (max-width: 1000px) { .employee-list { grid-template-columns: minmax(0, 1fr); } }
@media (max-width: 760px) { .employee-filter-card :deep(.el-form-item:first-child) { margin-bottom: 14px; } }
</style>
