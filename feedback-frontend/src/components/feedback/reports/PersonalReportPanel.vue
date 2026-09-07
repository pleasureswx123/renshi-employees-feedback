<script setup>
defineProps({ report: { type: Object, required: true } })
const statuses = { NOT_APPLICABLE: '不适用', MISSING: '缺失关系', PARTIAL: '部分提交', COMPLETE: '全部提交' }
const scoreText = score => score ?? '数据不足'
</script>

<template>
  <div class="personal-report">
    <h2>{{ report.targetName }} · 得分详情</h2>
    <p>{{ report.targetDeptName || '未设置部门' }} · 完成 {{ report.submittedCount }}/{{ report.expectedCount }} 份（{{ report.completionRate }}%）</p>
    <el-alert v-if="report.hasMissingData" title="存在未完成任务或漏答，请结合数据覆盖情况阅读得分。" type="warning" :closable="false" />
    <el-alert :title="report.onlySelfEvaluation ? '仅自评：发布时仅配置本人评价，最终得分按自评及指标权重计算。' : '最终得分来自他评加权，自评仅供对照，不计入最终得分。'" type="info" :closable="false" show-icon />
    <el-descriptions :column="2" border>
      <el-descriptions-item label="最终得分">{{ scoreText(report.score) }}</el-descriptions-item>
      <el-descriptions-item label="计分方式">{{ report.onlySelfEvaluation ? '自评按指标权重合成' : '按发布时的关系、指标权重合成' }}</el-descriptions-item>
      <el-descriptions-item label="自评参考分">{{ scoreText(report.selfScore) }}</el-descriptions-item>
      <el-descriptions-item label="他评加权分">{{ scoreText(report.otherScore) }}</el-descriptions-item>
    </el-descriptions>
    <h3>指标得分</h3>
    <p class="muted">最终得分由各项指标最终得分按指标权重加权汇总。他评先在同一关系内取平均，再按有效关系权重合成；缺失关系及实际使用的权重见下表。</p>
    <el-table :data="report.indicators" border>
      <el-table-column prop="indicatorName" label="指标" min-width="150" />
      <el-table-column prop="weight" label="权重（%）" width="110" />
      <el-table-column v-for="col in [{ key: 'score', label: '指标最终得分' }, { key: 'selfScore', label: '自评参考分' }, { key: 'otherScore', label: '他评加权分' }]" :key="col.key" :label="col.label" min-width="100">
        <template #default="{ row }">{{ scoreText(row[col.key]) }}</template>
      </el-table-column>
    </el-table>
    <template v-for="indicator in report.indicators" :key="indicator.indicatorId">
      <h3>{{ indicator.indicatorName }} · 关系与实际权重</h3>
      <el-table :data="indicator.relations" border>
        <el-table-column prop="relationName" label="关系" min-width="100" />
        <el-table-column label="完成情况" min-width="125"><template #default="{ row }">{{ statuses[row.status] }}（{{ row.submittedCount }}/{{ row.expectedCount }}）</template></el-table-column>
        <el-table-column label="关系得分" width="105"><template #default="{ row }">{{ scoreText(row.score) }}</template></el-table-column>
        <el-table-column prop="originalWeight" label="原权重（%）" width="115" />
        <el-table-column prop="effectiveWeight" label="实际权重（%）" width="130" />
        <el-table-column prop="missingAnswerCount" label="计分题漏答" width="110" />
      </el-table>
    </template>
    <h3>题目明细</h3>
    <p class="muted">题目均分仅统计已提交且有答案的记录；指标分母保留全部计分题满分。文字回答需单独的原始答案权限。</p>
    <el-table :data="report.questions" border>
      <el-table-column prop="title" label="题目" min-width="230" />
      <el-table-column prop="relationName" label="关系" width="90" />
      <el-table-column label="已答 / 已交" width="115"><template #default="{ row }">{{ row.answeredCount }} / {{ row.submittedCount }}</template></el-table-column>
      <el-table-column label="原始均分 / 满分" width="150"><template #default="{ row }">{{ row.isScored ? `${row.rawAverage ?? '—'} / ${row.maxScore}` : '不计分' }}</template></el-table-column>
      <el-table-column label="百分制" width="105"><template #default="{ row }">{{ row.score ?? '—' }}</template></el-table-column>
      <el-table-column prop="missingAnswerCount" label="漏答数" width="85" />
    </el-table>
  </div>
</template>

<style scoped>
.personal-report { display: grid; gap: 16px; min-width: 0; }
h2, h3, p { margin: 0; overflow-wrap: anywhere; }
.muted { color: var(--fb-text-regular, #606266); line-height: 1.6; }
</style>
