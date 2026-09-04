<script setup>
import CircleCheckIcon from '@iconify-vue/lucide/circle-check'
import ClockIcon from '@iconify-vue/lucide/clock-3'
import EyeIcon from '@iconify-vue/lucide/eye'
import LockKeyholeIcon from '@iconify-vue/lucide/lock-keyhole'
import PencilLineIcon from '@iconify-vue/lucide/pencil-line'
import SaveIcon from '@iconify-vue/lucide/save'
import UserRoundIcon from '@iconify-vue/lucide/user-round'
import { usePermissionStore } from '@/stores/permission'
import { TASK_STATUS_LABELS } from '@/utils/answerSheet'
import { formatDateTime } from '@/utils/displayFormat'

defineProps({ task: { type: Object, required: true }, showProject: Boolean })
defineEmits(['open'])
const permission = usePermissionStore()
</script>

<template>
  <el-card class="employee-task-card" shadow="never">
    <div class="task-card-content">
      <div class="task-identity">
        <p v-if="showProject" class="task-project">{{ task.projectName }}</p>
        <h3><UserRoundIcon width="20" height="20" class="target-icon" aria-hidden="true" /><span>{{ task.targetName }}</span></h3>
        <p>{{ task.targetDeptName || '未配置部门' }} · {{ task.relationName }}评价</p>
        <small v-if="task.submittedTime">提交时间：{{ formatDateTime(task.submittedTime) }}</small>
        <small v-else-if="task.savedTime">最近暂存：{{ formatDateTime(task.savedTime) }}</small>
      </div>
      <div class="task-card-actions">
        <el-tag :type="task.status === 'SUBMITTED' ? 'success' : task.status === 'CLOSED_INCOMPLETE' ? 'info' : 'warning'">
          <span class="task-status"><component :is="task.status === 'SUBMITTED' ? CircleCheckIcon : task.status === 'CLOSED_INCOMPLETE' ? LockKeyholeIcon : task.status === 'DRAFT' ? SaveIcon : ClockIcon" width="13" height="13" aria-hidden="true" />{{ TASK_STATUS_LABELS[task.status] }}</span>
        </el-tag>
        <el-button
          v-if="task.status === 'SUBMITTED' && permission.hasPermission('feedback:history:view')"
          :icon="EyeIcon"
          @click="$emit('open', task)"
        >查看答案</el-button>
        <el-button
          v-else-if="task.projectStatus === 'ACTIVE' && ['PENDING', 'DRAFT'].includes(task.status)"
          type="primary"
          :icon="PencilLineIcon"
          :disabled="!permission.hasPermission('feedback:task:view')"
          @click="$emit('open', task)"
        >{{ task.status === 'DRAFT' ? '继续评价' : '开始评价' }}</el-button>
      </div>
    </div>
  </el-card>
</template>

<style scoped>
.task-card-content { display: grid; gap: 18px; }
.task-identity { min-width: 0; overflow-wrap: anywhere; }
.task-identity h3 { display: flex; align-items: center; gap: 6px; margin: 0 0 8px; font-size: 18px; font-weight: 600; }
.target-icon { flex-shrink: 0; color: var(--el-color-primary); }
.task-status { display: inline-flex; align-items: center; gap: 4px; }
.task-identity p, .task-identity small { color: var(--fb-text-muted, #64748b); line-height: 1.6; }
.task-project { margin-top: 0; }
.task-card-actions { display: flex; gap: 12px; align-items: center; justify-content: space-between; padding-top: 16px; border-top: 1px solid var(--fb-border, #edf0f5); }
@media (max-width: 600px) {
  .task-card-content { align-items: stretch; flex-direction: column; }
  .task-card-actions { justify-content: space-between; }
}
</style>
