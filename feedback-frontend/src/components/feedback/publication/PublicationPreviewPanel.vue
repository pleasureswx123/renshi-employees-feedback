<script setup>
defineProps({
  preview: { type: Object, required: true },
  issues: { type: Array, default: () => [] },
  ready: Boolean
})
</script>

<template>
  <section class="preview-panel">
    <div class="section-heading">
      <div>
        <h2>4. 发布检查与任务预览</h2>
        <p>以下为最近一次保存后的检查结果，修改配置后请重新保存。</p>
      </div>
      <el-tag :type="ready ? 'success' : 'warning'">
        {{ ready ? '可以发布' : `待处理 ${issues.length} 项` }}
      </el-tag>
    </div>

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
      <el-table-column prop="targetUserId" label="被评价人ID" min-width="120" />
      <el-table-column prop="selfCount" label="自评" width="90" />
      <el-table-column prop="nonSelfCount" label="他评" width="90" />
      <el-table-column prop="assignmentCount" label="任务合计" width="110" />
    </el-table>

    <el-alert
      v-if="!issues.length"
      title="问卷、指标、人员、关系和任务配置已通过发布前检查。"
      type="success"
      :closable="false"
      show-icon
    />
    <el-table v-else :data="issues" size="small" empty-text="没有待处理问题">
      <el-table-column prop="message" label="待处理问题" min-width="280" />
      <el-table-column prop="path" label="位置" min-width="180" />
      <el-table-column prop="code" label="问题码" min-width="220" show-overflow-tooltip />
    </el-table>
  </section>
</template>

<style scoped>
.preview-panel { display: grid; gap: 18px; }
.section-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.section-heading h2, .section-heading p { margin: 0; }
.section-heading h2 { font-size: 18px; }
.section-heading p { margin-top: 6px; color: #64748b; font-size: 13px; }
</style>
