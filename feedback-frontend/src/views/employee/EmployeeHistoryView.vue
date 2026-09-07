<script setup>
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { listMyHistory } from '@/api/feedback/tasks'
import EmployeeTaskCard from '@/components/feedback/EmployeeTaskCard.vue'
import WorkspaceIcon from '@/components/WorkspaceIcon.vue'

const router = useRouter()
const form = ref()
const filters = reactive({ keyword: '' })
const rows = ref([])
const total = ref(0)
const pageNum = ref(1)
const loading = ref(false)
const error = ref('')
let requestId = 0

async function load(page = pageNum.value) {
  const id = ++requestId
  loading.value = true
  pageNum.value = page
  error.value = ''
  try {
    const response = await listMyHistory({ pageNum: page, pageSize: 12, keyword: filters.keyword.trim() })
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
  <section class="employee-history">
    <header class="history-heading"><div class="history-heading-icon"><WorkspaceIcon name="history" /></div><div>
      <h1 class="page-heading">我评价的</h1>
      <p class="page-description">查看你已提交的评价记录，已提交答案不可修改。</p>
    </div></header>
    <el-card shadow="never" class="history-filter-card">
    <el-form ref="form" :model="filters" inline class="history-filter workspace-filter" @keydown.enter.prevent="search">
      <el-form-item label="项目名称" prop="keyword" :rules="[{ max: 200, message: '最多输入200字' }]">
        <el-input v-model="filters.keyword" clearable placeholder="搜索项目名称" aria-label="搜索项目名称" />
      </el-form-item>
      <el-form-item><el-button type="primary" :loading="loading" @click="search"><WorkspaceIcon name="search" />查询</el-button></el-form-item>
    </el-form>
    </el-card>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <div v-loading="loading" class="history-list">
      <el-card v-if="!rows.length && !loading && !error" shadow="never" class="empty-history">
        <el-empty description="还没有已提交的评价" :image-size="110"><p class="page-description">完成并提交评价后，可在这里查看记录。</p></el-empty>
      </el-card>
      <EmployeeTaskCard v-for="task in rows" :key="task.assignmentId" :task="task" show-project horizontal @open="router.push(`/employee/reviews/${task.assignmentId}`)" />
    </div>
    <el-pagination v-if="total > 12" :current-page="pageNum" :page-size="12" :total="total" layout="prev, pager, next" :disabled="loading" @current-change="load" />
  </section>
</template>

<style scoped>
.employee-history { display: grid; gap: 24px; max-width: 1200px; margin: auto; padding-top: 12px; }
.history-heading { display: flex; align-items: center; gap: 16px; padding: 8px 0; }
.history-heading-icon { display: grid; place-items: center; flex: none; width: 52px; height: 52px; border-radius: 16px; background: var(--el-color-primary-light-9); color: var(--el-color-primary); font-size: 26px; }
.history-heading .page-heading { margin: 0 0 8px; font-size: 26px; }
.history-heading .page-description { margin: 0; line-height: 1.7; }
.history-filter-card { border-radius: 12px; }
.history-filter-card .history-filter { margin: 0; padding: 0; border: 0; }
.history-filter-card:deep(.el-form-item) { margin-bottom: 0; }
.history-list { min-height: 120px; display: grid; grid-template-columns: minmax(0, 1fr); gap: 16px; }
.empty-history { grid-column: 1 / -1; }
@media (max-width: 760px) {
  .employee-history { gap: 18px; padding-top: 0; }
  .history-heading { align-items: flex-start; gap: 12px; }
  .history-heading .page-heading { font-size: 23px; }
  .history-filter-card:deep(.el-form-item:first-child) { margin-bottom: 14px; }
}
</style>
