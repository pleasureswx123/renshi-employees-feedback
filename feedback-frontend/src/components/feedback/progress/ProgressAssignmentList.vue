<script setup>
defineProps({
  rows: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false }
})

const statusMap = {
  PENDING: { label: '未开始', type: 'info' },
  DRAFT: { label: '已暂存', type: 'warning' },
  SUBMITTED: { label: '已提交', type: 'success' },
  CLOSED_INCOMPLETE: { label: '关闭未完成', type: 'danger' }
}

function statusMeta(status) {
  return statusMap[status] || { label: status, type: 'info' }
}

function displayTime(row) {
  if (row.status === 'SUBMITTED') return row.submittedTime || '—'
  if (row.status === 'DRAFT') return row.savedTime || '—'
  if (row.status === 'CLOSED_INCOMPLETE') return row.closedTime || '—'
  return '—'
}
</script>

<template>
  <div class="assignment-list">
    <el-table v-loading="loading" :data="rows" class="desktop-table" empty-text="当前筛选下暂无回收明细">
      <el-table-column label="被评价人" min-width="170">
        <template #default="{ row }">
          <strong>{{ row.targetName }}</strong>
          <small>{{ row.targetDeptName || '—' }}</small>
        </template>
      </el-table-column>
      <el-table-column label="评价人" min-width="170">
        <template #default="{ row }">
          <strong>{{ row.evaluatorName }}</strong>
          <small>{{ row.evaluatorDeptName || '—' }}</small>
        </template>
      </el-table-column>
      <el-table-column prop="relationName" label="关系" min-width="110" />
      <el-table-column label="任务状态" min-width="130">
        <template #default="{ row }">
          <el-tag :type="statusMeta(row.status).type">{{ statusMeta(row.status).label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态时间" min-width="180">
        <template #default="{ row }">{{ displayTime(row).replace?.('T', ' ') || displayTime(row) }}</template>
      </el-table-column>
    </el-table>

    <div v-loading="loading" class="mobile-cards">
      <el-empty v-if="!rows.length" description="当前筛选下暂无回收明细" :image-size="72" />
      <article v-for="row in rows" :key="row.assignmentId" class="assignment-card">
        <header>
          <strong>{{ row.targetName }}</strong>
          <el-tag :type="statusMeta(row.status).type" size="small">{{ statusMeta(row.status).label }}</el-tag>
        </header>
        <dl>
          <div><dt>被评价人部门</dt><dd>{{ row.targetDeptName || '—' }}</dd></div>
          <div><dt>评价人</dt><dd>{{ row.evaluatorName }}</dd></div>
          <div><dt>评价人部门</dt><dd>{{ row.evaluatorDeptName || '—' }}</dd></div>
          <div><dt>关系</dt><dd>{{ row.relationName }}</dd></div>
          <div><dt>状态时间</dt><dd>{{ displayTime(row).replace?.('T', ' ') || displayTime(row) }}</dd></div>
        </dl>
      </article>
    </div>
  </div>
</template>

<style scoped>
.desktop-table strong,
.desktop-table small { display: block; }
.desktop-table small { margin-top: 4px; color: #64748b; }
.mobile-cards { display: none; }
.assignment-card { min-width: 0; padding: 16px; border: 1px solid #e2e8f0; border-radius: 10px; background: #fff; }
.assignment-card header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
dl { display: grid; gap: 8px; margin: 14px 0 0; }
dl div { display: grid; grid-template-columns: 110px minmax(0, 1fr); gap: 8px; }
dt { color: #64748b; }
dd { min-width: 0; margin: 0; overflow-wrap: anywhere; }
@media (max-width: 760px) {
  .desktop-table { display: none; }
  .mobile-cards { display: grid; gap: 12px; }
}
</style>
