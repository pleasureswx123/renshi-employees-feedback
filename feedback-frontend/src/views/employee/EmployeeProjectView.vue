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
      <header class="project-header"><div class="project-heading-icon"><ClipboardListIcon width="28" height="28" aria-hidden="true" /></div><div class="project-heading-copy">
        <h1 class="page-heading project-heading">{{ project.projectName }}</h1>
        <p class="page-description">逐人填写、独立提交；提交后的答案不可修改。</p>
      </div></header>
      <el-alert v-if="project.projectStatus === 'COMPLETED'" title="项目已完成，未提交任务已关闭，不能继续答题。" type="info" :closable="false" />
      <el-card shadow="never" class="my-progress">
        <div class="progress-overview">
          <span class="progress-label"><ListChecksIcon width="18" height="18" aria-hidden="true" /><span>我的进度：已提交 {{ project.submittedCount }}/{{ project.totalCount }} 份</span></span>
          <div class="progress-counts"><span>待评价 <strong>{{ project.pendingCount }}</strong></span><span>已暂存 <strong>{{ project.draftCount }}</strong></span><span v-if="project.closedCount">已关闭未完成 <strong>{{ project.closedCount }}</strong></span></div>
        </div>
        <el-progress :percentage="project.totalCount ? Math.round(project.submittedCount / project.totalCount * 100) : 0" :stroke-width="6" />
      </el-card>
      <div class="task-list">
        <EmployeeTaskCard v-for="task in project.tasks" :key="task.assignmentId" :task="task" horizontal @open="openTask" />
      </div>
    </template>
  </section>
</template>

<style scoped>
.employee-project { display: grid; gap: 24px; max-width: 1200px; min-height: 240px; margin: auto; padding-top: 12px; }
.project-navigation { display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.project-navigation .el-button { margin-left: 0; border-radius: 8px; }
.project-header { display: flex; align-items: center; gap: 16px; padding: 8px 0; }
.project-heading-icon { display: grid; place-items: center; flex: none; width: 52px; height: 52px; border-radius: 16px; background: var(--el-color-primary-light-9); color: var(--el-color-primary); }
.project-heading-copy { min-width: 0; }
.project-heading { margin: 0 0 8px; font-size: 26px; overflow-wrap: anywhere; }
.project-header .page-description { margin: 0; line-height: 1.7; }
.my-progress { border-radius: 12px; }
.my-progress:deep(.el-card__body) { padding: 24px 28px; }
.progress-overview { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 16px; }
.progress-label { display: flex; align-items: center; gap: 8px; font-weight: 500; }
.progress-label > :first-child { flex-shrink: 0; }
.my-progress .el-progress { margin-top: 18px; }
.progress-counts { display: flex; flex-wrap: wrap; gap: 12px 24px; color: var(--fb-text-muted, #64748b); font-size: 13px; }
.progress-counts strong { margin-left: 6px; color: var(--el-text-color-primary); font-size: 17px; font-weight: 600; }
.task-list { display: grid; grid-template-columns: minmax(0, 1fr); gap: 16px; }
@media (max-width: 760px) {
  .employee-project { gap: 18px; padding-top: 0; }
  .project-header { align-items: flex-start; gap: 12px; }
  .project-heading { font-size: 23px; }
  .my-progress:deep(.el-card__body) { padding: 20px; }
}
</style>
