<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { getMyProject } from '@/api/feedback/tasks'
import EmployeeTaskCard from '@/components/feedback/EmployeeTaskCard.vue'

const route = useRoute()
const router = useRouter()
const project = ref(null)
const loading = ref(false)
const error = ref('')
let requestId = 0

async function load() {
  const id = ++requestId
  loading.value = true
  project.value = null
  error.value = ''
  try {
    const response = await getMyProject(route.params.projectId)
    if (id === requestId) project.value = response.data
  } catch (failure) {
    if (id === requestId) error.value = failure.message
  } finally {
    if (id === requestId) loading.value = false
  }
}

function openTask(task) {
  router.push(`/employee/${task.status === 'SUBMITTED' ? 'reviews' : 'tasks'}/${task.assignmentId}`)
}

watch(() => route.params.projectId, load, { immediate: true })
onBeforeUnmount(() => { requestId++ })
</script>

<template>
  <section v-loading="loading" class="employee-project">
    <el-button @click="router.push('/employee/todos')">返回我的待办</el-button>
    <el-button :loading="loading" @click="load">刷新进度</el-button>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <template v-if="project">
      <h1 class="page-heading">{{ project.projectName }}</h1>
      <p class="page-description">每份评价独立提交；提交后不可修改，其他人的评价可以继续填写。</p>
      <el-alert v-if="project.projectStatus === 'COMPLETED'" title="项目已完成，未提交任务已关闭，不能继续答题。" type="info" :closable="false" />
      <el-card shadow="never" class="my-progress">
        <span>我的进度：已提交 {{ project.submittedCount }}/{{ project.totalCount }} 份</span>
        <el-progress :percentage="Math.round(project.submittedCount / project.totalCount * 100)" />
        <small>待评价 {{ project.pendingCount }} · 已暂存 {{ project.draftCount }} · 已关闭未完成 {{ project.closedCount }}</small>
      </el-card>
      <div class="task-list">
        <EmployeeTaskCard v-for="task in project.tasks" :key="task.assignmentId" :task="task" @open="openTask" />
      </div>
    </template>
  </section>
</template>

<style scoped>
.employee-project { max-width: 1000px; min-height: 240px; margin: auto; }
.page-heading { margin-top: 24px; overflow-wrap: anywhere; }
.my-progress { margin: 24px 0; }
.my-progress .el-progress { margin: 12px 0; }
.my-progress small { color: #64748b; }
.task-list { display: grid; gap: 16px; }
.el-alert { margin-top: 16px; }
</style>
