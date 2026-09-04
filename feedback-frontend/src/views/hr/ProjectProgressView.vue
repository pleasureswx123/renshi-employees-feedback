<script setup>
import { ElMessage } from 'element-plus'
import { storeToRefs } from 'pinia'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import CompletionPrecheckDrawer from '@/components/feedback/progress/CompletionPrecheckDrawer.vue'
import ProgressAssignmentList from '@/components/feedback/progress/ProgressAssignmentList.vue'
import ProgressKpiGrid from '@/components/feedback/progress/ProgressKpiGrid.vue'
import { usePermissionStore } from '@/stores/permission'
import { useProjectProgressStore } from '@/stores/projectProgress'

const route = useRoute()
const permissionStore = usePermissionStore()
const store = useProjectProgressStore()
const { filters } = storeToRefs(store)
const filterFormRef = ref()
const drawerVisible = ref(false)
const completionEntry = ref('normal')
const errorMessage = ref('')

const statusOptions = [
  { value: 'PENDING', label: '未开始' },
  { value: 'DRAFT', label: '已暂存' },
  { value: 'SUBMITTED', label: '已提交' },
  { value: 'CLOSED_INCOMPLETE', label: '关闭未完成' }
]
const statusLabels = { PREPARING: '准备阶段', ACTIVE: '进行阶段', COMPLETED: '已完成' }
const backLabel = computed(() => permissionStore.hasPermission('feedback:project:list') ? '返回项目列表' : '返回评价进度入口')
const showCompletionAction = computed(() =>
  permissionStore.hasPermission('feedback:project:complete') &&
  store.project?.projectStatus === 'ACTIVE' &&
  store.dataScopeComplete
)
const remainingCount = computed(() => (store.summary?.pendingCount || 0) + (store.summary?.draftCount || 0))
const allSubmitted = computed(() => store.summary?.totalCount > 0 && store.summary.submittedCount === store.summary.totalCount)
const canStartCompletion = computed(() => showCompletionAction.value && store.summary?.totalCount > 0 &&
  !store.completionResultUnknown && !store.loading && !store.prechecking && !store.completing)

function validatePositiveInteger(_rule, value, callback) {
  if (value === null || value === undefined || value === '') return callback()
  if (!Number.isInteger(value) || value < 1) return callback(new Error('用户ID必须为正整数'))
  callback()
}

const filterRules = {
  evaluatorUserId: [{ validator: validatePositiveInteger, trigger: 'change' }],
  targetUserId: [{ validator: validatePositiveInteger, trigger: 'change' }]
}

async function load(projectId, options) {
  errorMessage.value = ''
  try {
    await store.load(projectId, options)
  } catch (error) {
    errorMessage.value = error.message || '评价进度加载失败'
  }
}

async function search() {
  errorMessage.value = ''
  try {
    await filterFormRef.value?.validate()
  } catch {
    return
  }
  try {
    await store.search()
  } catch (error) {
    errorMessage.value = error.message || '筛选失败'
  }
}

function resetFilters() {
  Object.assign(filters.value, {
    evaluatorUserId: null,
    targetUserId: null,
    relationId: null,
    status: '',
    evaluatorKeyword: '',
    targetKeyword: '',
    pageNum: 1
  })
  filterFormRef.value?.clearValidate()
  search()
}

function filterByStatus(status) {
  filters.value.status = status
  filters.value.pageNum = 1
  search()
}

async function changePage(pageNum) {
  errorMessage.value = ''
  try {
    await store.changePage(pageNum)
  } catch (error) {
    errorMessage.value = error.message || '分页加载失败'
  }
}

async function openCompletionPrecheck(early = false) {
  if (!canStartCompletion.value || (early ? remainingCount.value === 0 : !allSubmitted.value)) return
  completionEntry.value = early ? 'early' : 'normal'
  try {
    const precheck = await store.precheckCompletion()
    if (precheck?.projectStatus === 'COMPLETED') drawerVisible.value = true
    else if (precheck?.canComplete && precheck.dataScopeComplete) drawerVisible.value = true
    else if (precheck) ElMessage.warning('最新预检未通过，当前不能完成项目')
  } catch {
    drawerVisible.value = false
  }
}

async function submitCompletion(reason) {
  try {
    const result = await store.complete(reason, {
      refreshProjectDetail: permissionStore.hasPermission('feedback:project:list')
    })
    if (result) {
      drawerVisible.value = false
      ElMessage.success(result.alreadyCompleted ? '项目此前已完成，已刷新最终状态' : '项目已完成')
    }
  } catch {
    if (!store.precheck) drawerVisible.value = false
  }
}

async function recheckCompletionResult() {
  errorMessage.value = ''
  try {
    const result = await store.recheckCompletionResult()
    if (result?.projectStatus === 'COMPLETED' && store.precheck) drawerVisible.value = true
  } catch (error) {
    errorMessage.value = error.message || '完成结果核对失败'
  }
}

watch(
  () => route.params.projectId,
  projectId => {
    if (!projectId) return
    if (store.projectId !== Number(projectId)) store.reset()
    load(Number(projectId), { force: true })
  },
  { immediate: true }
)

onBeforeUnmount(() => { drawerVisible.value = false })
</script>

<template>
  <section class="progress-page">
    <header class="workspace-page-header workspace-detail-header">
      <div class="workspace-detail-heading">
        <el-button
          class="workspace-detail-back" text :aria-label="backLabel" :title="backLabel"
          @click="$router.push(permissionStore.hasPermission('feedback:project:list') ? '/hr/projects' : '/hr/progress')"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="m10 6-6 6 6 6M4 12h16" />
          </svg>
          <span>返回</span>
        </el-button>
        <el-divider direction="vertical" class="workspace-detail-divider" />
        <div class="workspace-detail-title">
          <h1>评价进度</h1>
          <p class="workspace-detail-project">
            <span class="workspace-detail-project-label">所属项目</span>
            <span class="workspace-detail-project-name" :title="store.project?.projectName">{{ store.project?.projectName || '加载中…' }}</span>
          </p>
        </div>
      </div>
      <div v-if="store.project" class="project-actions">
        <el-tag :type="store.project.projectStatus === 'ACTIVE' ? 'success' : 'info'">
          {{ statusLabels[store.project.projectStatus] || store.project.projectStatus }}
        </el-tag>
        <el-button
          v-if="store.project.projectStatus === 'COMPLETED' && permissionStore.hasPermission('feedback:report:view')"
          type="primary" @click="$router.push(`/hr/projects/${route.params.projectId}/reports`)"
        >查看报告</el-button>
        <div v-if="showCompletionAction" class="completion-actions">
          <span class="completion-hint" role="status">
            <template v-if="remainingCount">还有 {{ remainingCount }} 份未提交</template>
            <template v-else-if="allSubmitted">全部评价已提交</template>
            <template v-else>暂无可完成的评价任务</template>
          </span>
          <el-button
            :type="allSubmitted ? 'danger' : ''"
            :loading="store.prechecking && completionEntry === 'normal'"
            :disabled="!canStartCompletion || !allSubmitted"
            @click="openCompletionPrecheck(false)"
          >完成项目</el-button>
          <el-button
            v-if="remainingCount > 0"
            link type="danger"
            :loading="store.prechecking && completionEntry === 'early'"
            :disabled="!canStartCompletion"
            @click="openCompletionPrecheck(true)"
          >提前结束</el-button>
        </div>
      </div>
    </header>
    <p class="progress-hint">查看评价任务的填写与提交情况。筛选只影响下方任务明细，不改变顶部统计。</p>

    <el-alert
      v-if="!store.dataScopeComplete && store.scopeMessage"
      :title="store.scopeMessage"
      description="下方统计只覆盖当前可见的被评价人，不能代表整个项目。"
      type="warning"
      :closable="false"
      show-icon
    />
    <div v-if="store.completionIssue" class="completion-issue">
      <el-alert
        :title="store.completionIssue.message"
        :type="['PROJECT_COMPLETION_SCOPE_FORBIDDEN', 'COMPLETION_RECHECK_ACTIVE'].includes(store.completionIssue.code) ? 'warning' : 'error'"
        :closable="false"
        show-icon
      />
      <el-button
        v-if="store.completionResultUnknown"
        type="primary"
        :loading="store.verifyingCompletion"
        :disabled="store.verifyingCompletion"
        @click="recheckCompletionResult"
      >
        重新核对
      </el-button>
    </div>
    <el-alert v-if="errorMessage" :title="errorMessage" type="error" :closable="false" show-icon />

    <el-skeleton v-if="store.loading && !store.summary" :rows="6" animated />
    <template v-else-if="store.summary">
      <ProgressKpiGrid
        :summary="store.summary"
        :active-status="filters.status"
        @filter="filterByStatus"
      />

      <el-card shadow="never" class="detail-card">
        <el-form ref="filterFormRef" :model="filters" :rules="filterRules" label-position="top" class="filter-form">
          <el-form-item label="评价人姓名">
            <el-input v-model="filters.evaluatorKeyword" maxlength="100" clearable placeholder="输入评价人姓名" @keyup.enter="search" />
          </el-form-item>
          <el-form-item label="被评价人姓名">
            <el-input v-model="filters.targetKeyword" maxlength="100" clearable placeholder="输入被评价人姓名" @keyup.enter="search" />
          </el-form-item>
          <el-form-item label="评价人用户ID" prop="evaluatorUserId">
            <el-input-number v-model="filters.evaluatorUserId" :min="1" :step="1" step-strictly :controls="false" placeholder="精确ID" />
          </el-form-item>
          <el-form-item label="被评价人用户ID" prop="targetUserId">
            <el-input-number v-model="filters.targetUserId" :min="1" :step="1" step-strictly :controls="false" placeholder="精确ID" />
          </el-form-item>
          <el-form-item label="评价关系">
            <el-select v-model="filters.relationId" clearable placeholder="全部关系">
              <el-option v-for="relation in store.relations" :key="relation.relationId" :label="relation.relationName" :value="relation.relationId" />
            </el-select>
          </el-form-item>
          <el-form-item label="任务状态">
            <el-select v-model="filters.status" clearable placeholder="全部状态">
              <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
          <el-form-item class="filter-actions">
            <el-button type="primary" :loading="store.loading" @click="search">查询</el-button>
            <el-button :disabled="store.loading" @click="resetFilters">重置</el-button>
          </el-form-item>
        </el-form>

        <ProgressAssignmentList :rows="store.rows" :loading="store.loading" />
        <div class="pagination-row">
          <el-pagination
            background
            layout="total, prev, pager, next"
            :total="store.total"
            :page-size="filters.pageSize"
            :current-page="filters.pageNum"
            @current-change="changePage"
          />
        </div>
      </el-card>
    </template>

    <CompletionPrecheckDrawer
      v-model="drawerVisible"
      :precheck="store.precheck"
      :completing="store.completing"
      @submit="submitCompletion"
    />
  </section>
</template>

<style scoped>
.progress-page { display: grid; gap: 20px; min-width: 0; }
.project-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; }
.completion-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; }
.completion-actions .el-button + .el-button { margin-left: 0; }
.completion-hint { color: var(--fb-text-muted, #64748b); font-size: 13px; line-height: 1.6; }
.progress-hint { margin: -8px 4px -4px; color: var(--fb-text-muted, #7b8798); font-size: 13px; line-height: 1.8; }
.detail-card { min-width: 0; }
.completion-issue { display: flex; align-items: center; gap: 12px; }
.completion-issue:deep(.el-alert) { flex: 1; min-width: 0; }
.filter-form { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0 16px; }
.filter-form:deep(.el-select),
.filter-form :deep(.el-input-number) { width: 100%; }
.filter-actions { align-self: end; }
.pagination-row { display: flex; justify-content: flex-end; max-width: 100%; margin-top: 20px; overflow-x: auto; }
@media (max-width: 900px) { .filter-form { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 600px) {
  .project-actions { width: 100%; justify-content: space-between; }
  .filter-form { grid-template-columns: minmax(0, 1fr); }
  .pagination-row { justify-content: flex-start; }
  .pagination-row:deep(.el-pagination__total) { display: none; }
}
</style>
