<script setup>
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useProjectReportsStore } from '@/stores/projectReports'
import { formatTableDate } from '@/utils/displayFormat'
import WorkspaceIcon from '@/components/WorkspaceIcon.vue'
import { usePermissionStore } from '@/stores/permission'

const store = useProjectReportsStore()
const permission = usePermissionStore()
const form = ref()
const filters = reactive({ keyword: '', pageNum: 1, pageSize: 20 })
let active = true
async function search() {
  if (store.loading.projects) return
  if (!await form.value.validate().catch(() => false)) return
  if (!active) return
  filters.pageNum = 1
  await store.loadProjects({ ...filters })
}
function pageChanged(pageNum) { filters.pageNum = pageNum; store.loadProjects({ ...filters }) }
onMounted(() => store.loadProjects({ ...filters }))
onBeforeUnmount(() => { active = false; store.reset() })
</script>

<template>
  <section class="report-projects">
    <header class="reports-heading"><div class="reports-icon"><WorkspaceIcon name="report" /></div><div><h1 class="page-heading">评价报告</h1><p class="page-description">项目完成后生成报告，查看团队和个人得分。</p></div></header>
    <el-alert title="报告如何产生？" description="HR 在评价进度页确认完成项目后，在本页选择项目，报告会自动生成；已有报告直接展示。答卷全部提交后仍需手动完成项目；报告按发布时冻结的题目、指标和关系权重计算，只使用已提交答卷。" type="info" :closable="false" show-icon />
    <el-card shadow="never" class="reports-list-card">
      <el-form ref="form" :model="filters" inline class="workspace-filter">
        <el-form-item label="项目名称" prop="keyword" :rules="[{ max: 200, message: '最多200字' }]">
          <el-input v-model="filters.keyword" clearable maxlength="200" placeholder="输入项目名称" @keyup.enter="search" />
        </el-form-item>
        <el-form-item><el-button type="primary" :loading="store.loading.projects" :disabled="store.loading.projects" @click="search">查询</el-button></el-form-item>
      </el-form>
      <el-alert v-if="store.errors.projects" :title="store.errors.projects" type="error" :closable="false" />
      <el-table v-loading="store.loading.projects" :data="store.projects?.rows || []" empty-text="当前没有可查看的已完成项目">
        <template #empty>
          <el-empty :description="filters.keyword ? '没有匹配的已完成项目' : '当前没有可查看的已完成项目'" :image-size="80">
            <p class="empty-report-hint">全部提交不等于项目已完成，请先到评价进度页确认项目状态。</p>
            <el-button v-if="permission.hasPermission('feedback:project:list')" @click="$router.push('/hr/projects')">前往评价项目</el-button>
          </el-empty>
        </template>
        <el-table-column prop="projectName" label="项目名称" min-width="220" show-overflow-tooltip />
        <el-table-column prop="completedTime" label="完成时间" min-width="180" :formatter="formatTableDate" />
        <el-table-column label="操作" width="120"><template #default="{ row }"><el-button link type="primary" @click="$router.push(`/hr/projects/${row.projectId}/reports`)">查看报告</el-button></template></el-table-column>
      </el-table>
      <el-pagination class="pagination" layout="total, prev, pager, next" :total="store.projects?.total || 0" :current-page="filters.pageNum" :page-size="filters.pageSize" @current-change="pageChanged" />
    </el-card>
  </section>
</template>

<style scoped>
.report-projects { display: grid; gap: 24px; min-width: 0; max-width: 1440px; margin: auto; padding-top: 12px; }
.reports-heading { display: flex; align-items: center; gap: 16px; padding: 8px 0; }
.reports-icon { display: grid; place-items: center; flex: none; width: 52px; height: 52px; border-radius: 16px; background: var(--el-color-primary-light-9); color: var(--el-color-primary); font-size: 26px; }
.reports-heading h1 { margin: 0 0 8px; font-size: 26px; }
.reports-heading p { margin: 0; line-height: 1.7; }
.report-projects > .el-alert { padding: 16px 20px; border-radius: 12px; }
.reports-list-card { border-radius: 12px; }
.reports-list-card:deep(.el-table__cell) { padding-block: 16px; }
.empty-report-hint { margin: 0 0 16px; color: var(--fb-text-muted, #64748b); font-size: 13px; line-height: 1.7; }
.pagination { margin-top: 20px; }
</style>
