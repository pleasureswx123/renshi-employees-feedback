<script setup>
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import {
  createProject,
  listProjects,
  removeProject,
  updateProject
} from '@/api/feedback/projects'
import { ProjectStatus } from '@/constants/feedbackEnums'
import { usePermissionStore } from '@/stores/permission'

const router = useRouter()
const permissionStore = usePermissionStore()
const loading = ref(false)
const mutating = ref(false)
const dialogVisible = ref(false)
const dialogMode = ref('create')
const projectFormRef = ref()
const rows = ref([])
const total = ref(0)
const filters = reactive({ projectName: '', status: '', pageNum: 1, pageSize: 10 })
const projectForm = reactive({ projectId: null, projectName: '', description: '', lockVersion: 0 })
const projectRules = {
  projectName: [
    { required: true, message: '请填写项目名称', trigger: 'blur' },
    { max: 200, message: '项目名称不能超过200个字符', trigger: 'blur' }
  ]
}
const statusOptions = [
  { value: ProjectStatus.PREPARING, label: '准备阶段', type: 'info' },
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
  projectForm.projectId = null
  projectForm.projectName = ''
  projectForm.description = ''
  projectForm.lockVersion = 0
  projectFormRef.value?.clearValidate()
}

function openCreateDialog() {
  resetProjectForm()
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
        questionnaireTitle: projectForm.projectName
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
      <div>
        <h1 class="page-heading">评价项目</h1>
        <p class="page-description">创建并配置问卷、人员与关系；发布后可复核冻结配置。</p>
      </div>
      <el-button
        v-if="permissionStore.hasPermission('feedback:project:add')"
        type="primary"
        @click="openCreateDialog"
      >
        创建项目
      </el-button>
    </header>

    <el-card shadow="never">
      <el-form :model="filters" inline class="filter-form">
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
          <el-button type="primary" :loading="loading" @click="handleSearch">查询</el-button>
          <el-button :disabled="loading" @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>

      <el-table v-loading="loading" :data="rows" empty-text="暂无评价项目">
        <el-table-column prop="projectName" label="项目名称" min-width="220" show-overflow-tooltip />
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusMeta(row.status).type">{{ statusMeta(row.status).label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="createBy" label="创建人" width="140" />
        <el-table-column prop="createTime" label="创建时间" width="190" />
        <el-table-column prop="updateTime" label="最近更新" width="190" />
        <el-table-column label="操作" width="390" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === ProjectStatus.PREPARING && permissionStore.hasPermission('feedback:questionnaire:edit')"
              type="primary"
              link
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
              回收进度
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
      :title="dialogMode === 'create' ? '创建评价项目' : '编辑评价项目'"
      width="560px"
      destroy-on-close
      :close-on-click-modal="!mutating"
      :close-on-press-escape="!mutating"
      :show-close="!mutating"
      @closed="resetProjectForm"
    >
      <el-form
        ref="projectFormRef"
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
            :rows="4"
            maxlength="5000"
            show-word-limit
            placeholder="说明评价目的和适用范围"
          />
        </el-form-item>
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
  gap: 20px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
}

.filter-form {
  margin-bottom: 8px;
}

.pagination-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}

@media (max-width: 760px) {
  .page-header {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
