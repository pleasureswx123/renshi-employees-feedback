<script setup>
import { usePermissionStore } from '@/stores/permission'
import { TASK_STATUS_LABELS } from '@/utils/answerSheet'

defineProps({ task: { type: Object, required: true }, showProject: Boolean })
defineEmits(['open'])
const permission = usePermissionStore()
</script>

<template>
  <el-card class="employee-task-card" shadow="never">
    <div class="task-card-content">
      <div class="task-identity">
        <p v-if="showProject" class="task-project">{{ task.projectName }}</p>
        <h3>{{ task.targetName }}</h3>
        <p>{{ task.targetDeptName || '未配置部门' }} · {{ task.relationName }}评价</p>
        <small v-if="task.submittedTime">提交时间：{{ task.submittedTime.replace('T', ' ') }}</small>
        <small v-else-if="task.savedTime">最近暂存：{{ task.savedTime.replace('T', ' ') }}</small>
      </div>
      <div class="task-card-actions">
        <el-tag :type="task.status === 'SUBMITTED' ? 'success' : task.status === 'CLOSED_INCOMPLETE' ? 'info' : 'warning'">
          {{ TASK_STATUS_LABELS[task.status] }}
        </el-tag>
        <el-button
          v-if="task.status === 'SUBMITTED' && permission.hasPermission('feedback:history:view')"
          @click="$emit('open', task)"
        >查看答案</el-button>
        <el-button
          v-else-if="task.projectStatus === 'ACTIVE' && ['PENDING', 'DRAFT'].includes(task.status)"
          type="primary"
          :disabled="!permission.hasPermission('feedback:task:view')"
          @click="$emit('open', task)"
        >{{ task.status === 'DRAFT' ? '继续评价' : '开始评价' }}</el-button>
      </div>
    </div>
  </el-card>
</template>

<style scoped>
.task-card-content { display: flex; justify-content: space-between; gap: 20px; align-items: center; }
.task-identity { min-width: 0; overflow-wrap: anywhere; }
.task-identity h3 { margin: 0 0 8px; }
.task-identity p, .task-identity small { color: #64748b; line-height: 1.6; }
.task-project { margin-top: 0; }
.task-card-actions { display: flex; gap: 12px; align-items: center; flex-shrink: 0; }
@media (max-width: 600px) {
  .task-card-content { align-items: stretch; flex-direction: column; }
  .task-card-actions { justify-content: space-between; }
}
</style>
