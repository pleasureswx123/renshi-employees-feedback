<script setup>
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useProjectReportsStore } from '@/stores/projectReports'

const store = useProjectReportsStore()
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
    <div><h1 class="page-heading">评价报告</h1><p class="page-description">选择已完成项目，查看团队和个人得分。</p></div>
    <el-card shadow="never">
      <el-form ref="form" :model="filters" inline>
        <el-form-item label="项目名称" prop="keyword" :rules="[{ max: 200, message: '最多200字' }]">
          <el-input v-model="filters.keyword" clearable maxlength="200" @keyup.enter="search" />
        </el-form-item>
        <el-form-item><el-button type="primary" :loading="store.loading.projects" :disabled="store.loading.projects" @click="search">查询</el-button></el-form-item>
      </el-form>
      <el-alert v-if="store.errors.projects" :title="store.errors.projects" type="error" :closable="false" />
      <el-table v-loading="store.loading.projects" :data="store.projects?.rows || []" empty-text="当前没有可查看的已完成项目">
        <el-table-column prop="projectName" label="项目名称" min-width="220" />
        <el-table-column prop="completedTime" label="完成时间" min-width="180" />
        <el-table-column label="操作" width="120"><template #default="{ row }"><el-button link type="primary" @click="$router.push(`/hr/projects/${row.projectId}/reports`)">查看报告</el-button></template></el-table-column>
      </el-table>
      <el-pagination class="pagination" layout="total, prev, pager, next" :total="store.projects?.total || 0" :current-page="filters.pageNum" :page-size="filters.pageSize" @current-change="pageChanged" />
    </el-card>
  </section>
</template>

<style scoped>
.report-projects { display: grid; gap: 20px; min-width: 0; }
.pagination { margin-top: 20px; }
</style>
