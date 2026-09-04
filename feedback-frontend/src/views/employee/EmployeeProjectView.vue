<script setup>
import ArrowLeftIcon from '@iconify-vue/lucide/arrow-left'
import ClipboardListIcon from '@iconify-vue/lucide/clipboard-list'
import ListChecksIcon from '@iconify-vue/lucide/list-checks'
import RefreshCwIcon from '@iconify-vue/lucide/refresh-cw'
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
    <div class="project-navigation">
      <el-button :icon="ArrowLeftIcon" @click="router.push('/employee/todos')">返回我的待办</el-button>
      <el-button :icon="RefreshCwIcon" :loading="loading" @click="load">刷新进度</el-button>
    </div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <template v-if="project">
      <header class="workspace-page-header"><div>
        <h1 class="page-heading project-heading"><ClipboardListIcon width="22" height="22" class="project-icon" aria-hidden="true" /><span>{{ project.projectName }}</span></h1>
        <p class="page-description">每份评价独立提交；提交后不可修改，其他人的评价可以继续填写。</p>
      </div></header>
      <el-alert v-if="project.projectStatus === 'COMPLETED'" title="项目已完成，未提交任务已关闭，不能继续答题。" type="info" :closable="false" />
      <el-card shadow="never" class="my-progress">
        <span class="progress-label"><ListChecksIcon width="16" height="16" aria-hidden="true" /><span>我的进度：已提交 {{ project.submittedCount }}/{{ project.totalCount }} 份</span></span>
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
.employee-project { display: grid; gap: 18px; max-width: 1200px; min-height: 240px; margin: auto; }
.project-navigation { display: flex; gap: 12px; flex-wrap: wrap; }
.project-navigation .el-button { margin-left: 0; }
.project-heading { display: flex; align-items: center; gap: 8px; overflow-wrap: anywhere; }
.project-icon { flex-shrink: 0; color: var(--el-color-primary); }
.progress-label { display: flex; align-items: center; gap: 6px; }
.progress-label > :first-child { flex-shrink: 0; }
.my-progress .el-progress { margin: 12px 0; }
.my-progress small { color: var(--fb-text-muted, #64748b); }
.task-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
@media (max-width: 1000px) { .task-list { grid-template-columns: minmax(0, 1fr); } }
</style>
