<script setup>
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import {
  listSystemTemplates,
  createProject,
  listProjects,
  removeProject,
  updateProject
} from '@/api/feedback/projects'
import { ProjectStatus } from '@/constants/feedbackEnums'
import { usePermissionStore } from '@/stores/permission'
import WorkspaceIcon from '@/components/WorkspaceIcon.vue'
import { formatDateTime } from '@/utils/displayFormat'
import { useWorkspaceUiStore } from '@/stores/workspaceUi'

const router = useRouter()
const permissionStore = usePermissionStore()
const ui = useWorkspaceUiStore()
const loading = ref(false)
const mutating = ref(false)
const dialogVisible = ref(false)
const dialogMode = ref('create')
const projectFormRef = ref()
const rows = ref([])
const total = ref(0)
const filters = reactive({ projectName: '', status: '', pageNum: 1, pageSize: 10 })
const templates = ref([])
const templatesLoading = ref(false)
const templatesError = ref('')
const selectedTemplate = computed(() => templates.value.find(item => item.templateKey === projectForm.templateKey))
async function loadTemplates() {
  templatesLoading.value = true
  templatesError.value = ''
  try { const response = await listSystemTemplates(); templates.value = response.data || [] }
  catch (error) { templatesError.value = error.message || '模板加载失败，请重试' }
  finally { templatesLoading.value = false }
}
const projectForm = reactive({ templateKey: '', projectId: null, projectName: '', description: '', lockVersion: 0 })
const projectRules = {
  projectName: [
    { required: true, message: '请填写项目名称', trigger: 'blur' },
    { max: 200, message: '项目名称不能超过200个字符', trigger: 'blur' }
  ]
}
const statusOptions = [
  { value: ProjectStatus.PREPARING, label: '准备阶段', type: 'warning' },
  { value: ProjectStatus.ACTIVE, label: '进行阶段', type: 'success' },
  { value: ProjectStatus.COMPLETED, label: '已完成', type: 'info' }
]

function statusMeta(status) {
  return statusOptions.find(item => item.value === status) || { label: status, type: 'info' }
}

async function loadProjects() {
  if (loading.value) return
  loading.value = true
  try {
    const response = await listProjects({
      projectName: filters.projectName || undefined,
      status: filters.status || undefined,
      pageNum: filters.pageNum,
      pageSize: filters.pageSize
    })
    rows.value = response.rows || []
    total.value = Number(response.total || 0)
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  filters.pageNum = 1
  loadProjects()
}

function handleReset() {
  filters.projectName = ''
  filters.status = ''
  filters.pageNum = 1
  loadProjects()
}

function resetProjectForm() {
  projectForm.templateKey = ''
  projectForm.projectId = null
  projectForm.projectName = ''
  projectForm.description = ''
  projectForm.lockVersion = 0
  projectFormRef.value?.clearValidate()
}

function openCreateDialog() {
  resetProjectForm()
  loadTemplates()
  dialogMode.value = 'create'
  dialogVisible.value = true
}

function openEditDialog(row) {
  projectForm.projectId = row.projectId
  projectForm.projectName = row.projectName
  projectForm.description = row.description || ''
  projectForm.lockVersion = row.lockVersion
  dialogMode.value = 'edit'
  dialogVisible.value = true
}

async function submitProject() {
  if (mutating.value || !dialogVisible.value || !projectFormRef.value) return
  mutating.value = true
  try {
    const valid = await projectFormRef.value.validate().catch(() => false)
    if (!valid) return
    if (dialogMode.value === 'create') {
      const response = await createProject({
        projectName: projectForm.projectName,
        description: projectForm.description || null,
        questionnaireTitle: projectForm.projectName,
        ...(projectForm.templateKey ? { templateKey: projectForm.templateKey } : {})
      })
      ElMessage.success('项目已创建，正在进入问卷编辑器')
      dialogVisible.value = false
      await router.push(`/hr/projects/${response.data.projectId}/editor`)
      return
    }
    await updateProject(projectForm.projectId, {
      projectName: projectForm.projectName,
      description: projectForm.description || null,
      lockVersion: projectForm.lockVersion
    })
    ElMessage.success('项目已更新')
    dialogVisible.value = false
    await loadProjects()
  } catch (error) {
    // 请求拦截器负责接口错误提示，校验拒绝不会泄漏为未处理异常。
    if (!error?.__requestClassified) ElMessage.error(error?.message || '项目保存失败，请重试')
  } finally {
    mutating.value = false
  }
}

async function handleDelete(row) {
  await ElMessageBox.confirm(
    `确认删除准备阶段项目“${row.projectName}”吗？项目草稿将不再出现在列表中。`,
    '删除项目',
    { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }
  )
  await removeProject(row.projectId, row.lockVersion)
  ElMessage.success('项目已删除')
  if (rows.value.length === 1 && filters.pageNum > 1) filters.pageNum -= 1
  await loadProjects()
}

function handlePageChange(pageNum) {
  filters.pageNum = pageNum
  loadProjects()
}

onMounted(loadProjects)
</script>

<template>
  <section class="project-page">
    <header class="page-header">
      <div class="project-heading-group">
        <div class="project-heading-icon"><WorkspaceIcon name="project" /></div>
        <div>
        <h1 class="page-heading">评价项目</h1>
        <p class="page-description">配置问卷与参评人员，发布评价并跟进评价进度。</p>
        </div>
      </div>
      <el-button
        v-if="permissionStore.hasPermission('feedback:project:add')"
        type="primary"
        @click="openCreateDialog"
      >
        <WorkspaceIcon name="plus" />创建项目
      </el-button>
    </header>

    <el-card shadow="never" class="project-filter-card">
      <el-form :model="filters" inline class="filter-form workspace-filter">
        <el-form-item label="项目名称">
          <el-input
            v-model="filters.projectName"
            clearable
            placeholder="输入项目名称"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item label="项目状态">
          <el-select v-model="filters.status" clearable placeholder="全部状态" style="width: 160px">
            <el-option
              v-for="item in statusOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="handleSearch"><WorkspaceIcon name="search" />查询</el-button>
          <el-button :disabled="loading" @click="handleReset"><WorkspaceIcon name="refresh" />重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="project-list-card">
      <div class="list-caption"><h2>项目列表</h2><span>共 {{ total }} 个项目</span></div>
      <el-table v-loading="loading" :data="rows" empty-text="暂无评价项目" class="project-table">
        <el-table-column prop="projectName" label="项目名称" min-width="220" show-overflow-tooltip>
          <template #default="{ row }"><div class="project-name-cell"><WorkspaceIcon name="project" /><strong>{{ row.projectName }}</strong></div></template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusMeta(row.status).type">{{ statusMeta(row.status).label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="createBy" label="创建人" width="90" show-overflow-tooltip />
        <el-table-column label="创建 / 更新时间" width="215" class-name="date-column">
          <template #default="{ row }"><div class="project-times"><span>创建 {{ formatDateTime(row.createTime) }}</span><span>更新 {{ formatDateTime(row.updateTime) }}</span></div></template>
        </el-table-column>
        <el-table-column label="操作" width="320" :fixed="ui.compact ? false : 'right'">
          <template #default="{ row }">
            <div class="project-row-actions">
            <el-button
              v-if="row.status === ProjectStatus.PREPARING && permissionStore.hasPermission('feedback:questionnaire:edit')"
              type="primary"
              plain
              size="small"
              @click="router.push(`/hr/projects/${row.projectId}/editor`)"
            >
              编辑问卷
            </el-button>
            <el-button
              v-if="permissionStore.hasAnyPermission(['feedback:participant:manage', 'feedback:project:publish'])"
              type="primary"
              link
              @click="router.push(`/hr/projects/${row.projectId}/publication`)"
            >
              {{ row.status === ProjectStatus.PREPARING ? '配置并发布' : '查看发布配置' }}
            </el-button>
            <el-button
              v-if="[ProjectStatus.ACTIVE, ProjectStatus.COMPLETED].includes(row.status) && permissionStore.hasPermission('feedback:progress:view')"
              type="primary"
              link
              @click="router.push(`/hr/projects/${row.projectId}/progress`)"
            >
              评价进度
            </el-button>
            <el-button
              v-if="row.status === ProjectStatus.COMPLETED && permissionStore.hasPermission('feedback:report:view')"
              type="primary" link @click="router.push(`/hr/projects/${row.projectId}/reports`)"
            >查看报告</el-button>
            <el-button
              v-if="row.status === ProjectStatus.PREPARING && permissionStore.hasPermission('feedback:project:edit')"
              link
              @click="openEditDialog(row)"
            >
              编辑项目
            </el-button>
            <el-button
              v-if="row.status === ProjectStatus.PREPARING && permissionStore.hasPermission('feedback:project:remove')"
              type="danger"
              link
              @click="handleDelete(row)"
            >
              删除
            </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-row">
        <el-pagination
          background
          layout="total, prev, pager, next"
          :total="total"
          :page-size="filters.pageSize"
          :current-page="filters.pageNum"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      class="project-dialog"
      :title="dialogMode === 'create' ? '创建评价项目' : '编辑评价项目'"
      width="min(560px, 94vw)"
      destroy-on-close
      :close-on-click-modal="!mutating"
      :close-on-press-escape="!mutating"
      :show-close="!mutating"
      @closed="resetProjectForm"
    >
      <el-form
        ref="projectFormRef"
        class="project-create-form"
        :model="projectForm"
        :rules="projectRules"
        :disabled="mutating"
        label-position="top"
      >
        <el-form-item label="项目名称" prop="projectName">
          <el-input v-model="projectForm.projectName" maxlength="200" show-word-limit @keyup.enter="submitProject" />
        </el-form-item>
        <el-form-item label="项目说明">
          <el-input
            v-model="projectForm.description"
            type="textarea"
            :rows="2"
            maxlength="5000"
            show-word-limit
            placeholder="说明评价目的和适用范围"
          />
        </el-form-item>
        <template v-if="dialogMode === 'create'">
          <el-form-item label="问卷来源" prop="templateKey"><el-select v-model="projectForm.templateKey" :loading="templatesLoading" style="width: 100%"><el-option label="空白问卷 · 自行设计" value="" /><el-option v-for="item in templates" :key="item.templateKey" :value="item.templateKey" :label="item.name" /></el-select></el-form-item>
          <el-alert v-if="templatesError" :title="templatesError" type="error" :closable="false"><el-button link @click="loadTemplates">重试加载模板</el-button></el-alert>
          <section v-if="selectedTemplate" class="template-preview">
            <p class="template-summary">{{ selectedTemplate.description }}</p>
            <p>1–5分评分 · 补充建议不计分</p>
            <el-collapse><el-collapse-item title="查看题目、指标与评分说明" name="preview"><p>{{ selectedTemplate.scale.join(' / ') }}</p><div v-for="item in selectedTemplate.indicators" :key="item.name" class="template-indicator"><strong>{{ item.name }} · 权重 {{ item.weight }}%</strong><ol><li v-for="question in item.questions" :key="question">{{ question }}</li></ol></div><p>可选问答：请描述值得肯定的表现，以及建议改进的具体事项。</p></el-collapse-item></el-collapse>
            <p>创建后可独立修改题目和权重。参评人员及评价关系权重需在发布前配置。</p>
          </section>
        </template>
      </el-form>
      <template #footer>
        <el-button :disabled="mutating" @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="mutating" @click="submitProject">
          {{ dialogMode === 'create' ? '创建并编辑问卷' : '保存项目' }}
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.project-page {
  display: grid;
  gap: 16px;
  max-width: 1440px;
  margin: auto;
  padding-top: 4px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 8px 0;
}

.project-heading-group { display: flex; align-items: center; gap: 16px; min-width: 0; }
.project-heading-icon { display: grid; place-items: center; flex: none; width: 42px; height: 42px; border-radius: 12px; background: var(--el-color-primary-light-9); color: var(--el-color-primary); font-size: 26px; }
.page-header .page-heading { margin: 0 0 4px; font-size: 22px; }
.page-header .page-description { margin: 0; line-height: 1.7; }
.page-header > .el-button { min-height: 40px; border-radius: 8px; padding-inline: 20px; }
.project-filter-card, .project-list-card { border-radius: 12px; }
.project-filter-card .filter-form { margin: 0; padding: 0; border: 0; }
.project-filter-card:deep(.el-form-item) { margin-bottom: 0; }
.list-caption { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.list-caption h2 { margin: 0; font-size: 16px; font-weight: 600; }
.list-caption > span { color: var(--fb-text-muted, #64748b); font-size: 13px; }
.project-table:deep(th.el-table__cell) { padding: 10px 0; font-weight: 500; }
.project-table:deep(td.el-table__cell) { padding: 12px 0; }
.project-table:deep(.date-column) { color: var(--fb-text-muted, #64748b); font-size: 13px; }
.project-times { display: grid; gap: 4px; font-variant-numeric: tabular-nums; }
.project-name-cell { display: flex; align-items: center; gap: 10px; }
.project-name-cell > svg { color: var(--el-color-primary); }
.project-name-cell strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 14px; font-weight: 600; }
.project-row-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 8px 14px; }
.project-row-actions .el-button + .el-button { margin-left: 0; }
.project-row-actions .el-button { border-radius: 6px; }

.filter-form {
  margin-bottom: 8px;
}

.pagination-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

@media (max-width: 760px) {
  .project-page { gap: 18px; padding-top: 0; }
  .project-heading-group { align-items: flex-start; gap: 12px; }
  .page-header .page-heading { font-size: 23px; }
  .project-filter-card:deep(.el-form-item) { margin-bottom: 14px; }
  .project-filter-card:deep(.el-form-item:last-child) { margin-bottom: 0; }
  .page-header {
    align-items: flex-start;
    flex-direction: column;
  }
}
.template-preview { padding: 10px 12px; background: var(--el-fill-color-light); border-radius: 8px; line-height: 1.5; font-size: 13px; }
.template-preview p { margin: 4px 0; color: var(--fb-text-muted, #64748b); }
.template-indicator { margin-bottom: 10px; }
.template-indicator ol { margin: 4px 0; padding-left: 20px; }
.template-preview :deep(.el-collapse-item__header) { height: 36px; line-height: 1.5; background: transparent; }
.template-preview :deep(.el-collapse-item__wrap) { background: transparent; }
.template-preview :deep(.el-collapse-item__content) { padding-bottom: 8px; }
.project-create-form :deep(.el-form-item) { margin-bottom: 14px; }
.project-create-form :deep(.el-form-item__label) { margin-bottom: 4px; line-height: 22px; }
.project-filter-card :deep(.el-card__body), .project-list-card :deep(.el-card__body) { padding: 16px; }
</style>
