<script setup>
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { listMyHistory } from '@/api/feedback/tasks'
import EmployeeTaskCard from '@/components/feedback/EmployeeTaskCard.vue'

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
    <h1 class="page-heading">我评价的</h1>
    <p class="page-description">这里仅展示你已提交的评价，答案只读，不包含其他人对你的评价。</p>
    <el-form ref="form" :model="filters" inline class="history-filter" @keydown.enter.prevent="search">
      <el-form-item label="项目名称" prop="keyword" :rules="[{ max: 200, message: '最多输入200字' }]">
        <el-input v-model="filters.keyword" clearable placeholder="搜索项目名称" aria-label="搜索项目名称" />
      </el-form-item>
      <el-form-item><el-button type="primary" :loading="loading" @click="search">查询</el-button></el-form-item>
    </el-form>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <div v-loading="loading" class="history-list">
      <el-empty v-if="!rows.length && !loading && !error" description="还没有已提交的评价" />
      <EmployeeTaskCard v-for="task in rows" :key="task.assignmentId" :task="task" show-project @open="router.push(`/employee/reviews/${task.assignmentId}`)" />
    </div>
    <el-pagination v-if="total > 12" :current-page="pageNum" :page-size="12" :total="total" layout="prev, pager, next" :disabled="loading" @current-change="load" />
  </section>
</template>

<style scoped>
.employee-history { max-width: 1000px; margin: auto; }
.history-filter { margin-top: 24px; }
.history-list { min-height: 120px; display: grid; gap: 16px; margin-bottom: 16px; }
</style>
