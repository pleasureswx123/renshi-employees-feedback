<script setup>
import { publicationIssueDestination } from '@/utils/publicationWorkflow'

const props = defineProps({
  preview: { type: Object, required: true },
  issues: { type: Array, default: () => [] },
  ready: Boolean,
  targets: { type: Array, default: () => [] },
  participants: { type: Array, default: () => [] },
  stale: Boolean,
  editable: Boolean,
  canEditQuestionnaire: Boolean
})
const emit = defineEmits(['locate'])
function targetName(userId) {
  const target = props.targets.find(item => item.userId === userId)
  return target?.nickName || target?.userName || '未知员工'
}
function issueMessage(issue) {
  return issue.message.replace(/评价人ID (\d+)/g, (_, id) => {
    const participant = props.participants.find(item => String(item.userId) === id)
    return participant ? `评价人“${participant.nickName || participant.userName}”` : '已选评价人'
  })
}
</script>

<template>
  <section class="preview-panel">
    <div class="section-heading">
      <div>
        <h2>6. 检查并发布</h2>
        <p>确认谁被评价、谁来填写，以及将生成的任务。通过检查后即可发布。</p>
      </div>
      <el-tag :type="ready && !stale ? 'success' : 'warning'">
        {{ stale ? '需要重新检查' : ready ? '可以发布' : `待处理 ${issues.length} 项` }}
      </el-tag>
    </div>

    <el-alert v-if="stale" title="配置已有修改，以下检查结果已过期。请点击“保存并重新检查”，获取最新人数、任务和待处理问题。" type="warning" :closable="false" show-icon />
    <template v-else>
    <el-row :gutter="14">
      <el-col :xs="12" :sm="8">
        <el-statistic title="被评价人数" :value="preview.targetCount" />
      </el-col>
      <el-col :xs="12" :sm="8">
        <el-statistic title="评价人数" :value="preview.evaluatorCount" />
      </el-col>
      <el-col :xs="12" :sm="8">
        <el-statistic title="任务总数" :value="preview.assignmentCount" />
      </el-col>
    </el-row>

    <el-table :data="preview.targetSummaries" size="small" empty-text="尚无任务预览">
      <el-table-column label="被评价人" min-width="120"><template #default="{ row }">{{ targetName(row.targetUserId) }}</template></el-table-column>
      <el-table-column prop="selfCount" label="自评" width="90" />
      <el-table-column prop="nonSelfCount" label="他评" width="90" />
      <el-table-column prop="assignmentCount" label="任务合计" width="110" />
    </el-table>

    <el-alert
      v-if="ready && !issues.length"
      title="问卷、指标、人员、关系和任务配置已通过发布前检查。"
      type="success"
      :closable="false"
      show-icon
    />
    <el-table v-else :data="issues" size="small" empty-text="没有待处理问题">
      <el-table-column label="待处理问题" min-width="280"><template #default="{ row }">{{ issueMessage(row) }}</template></el-table-column>
      <el-table-column label="下一步" width="150">
        <template #default="{ row }">
          <el-button v-if="publicationIssueDestination(row) === 'editor' ? canEditQuestionnaire : editable" type="primary" link @click="emit('locate', row)">{{ publicationIssueDestination(row) === 'editor' ? '返回问卷处理' : '去处理' }}</el-button>
          <span v-else>请联系有权限的 HR</span>
        </template>
      </el-table-column>
    </el-table>
    </template>
  </section>
</template>

<style scoped>
.preview-panel { display: grid; gap: 18px; }
.section-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.section-heading h2, .section-heading p { margin: 0; }
.section-heading h2 { font-size: 18px; }
.section-heading p { margin-top: 6px; color: var(--fb-text-muted, #64748b); font-size: 13px; }
</style>
