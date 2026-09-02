<script setup>
import { onMounted, onBeforeUnmount, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { listMyProjects } from '@/api/feedback/tasks'

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
    <h1 class="page-heading">我的待办</h1>
    <p class="page-description">选择项目，按被评价人分别填写和提交评价。</p>
    <el-form ref="form" :model="filters" inline class="employee-filter" @keydown.enter.prevent="search">
      <el-form-item label="项目名称" prop="keyword" :rules="[{ max: 200, message: '最多输入200字' }]">
        <el-input v-model="filters.keyword" clearable placeholder="搜索项目名称" aria-label="搜索项目名称" />
      </el-form-item>
      <el-form-item><el-button type="primary" :loading="loading" @click="search">查询</el-button></el-form-item>
    </el-form>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <div v-loading="loading" class="employee-list">
      <el-empty v-if="!loading && !error && !rows.length" description="暂无待处理的评价任务" />
      <el-card v-for="project in rows" :key="project.projectId" shadow="never" class="project-card">
        <h2>{{ project.projectName }}</h2>
        <p>开始时间：{{ project.publishedTime?.replace('T', ' ') || '—' }}</p>
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
.employee-page { max-width: 1100px; margin: auto; }
.employee-filter { margin-top: 24px; }
.employee-list { display: grid; gap: 16px; min-height: 120px; margin: 16px 0; }
.project-card h2 { margin: 0; font-size: 20px; overflow-wrap: anywhere; }
.project-card p, .project-footer span { color: #64748b; line-height: 1.6; }
.project-footer { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-top: 18px; }
@media (max-width: 600px) { .project-footer { align-items: flex-start; flex-direction: column; } }
</style>
