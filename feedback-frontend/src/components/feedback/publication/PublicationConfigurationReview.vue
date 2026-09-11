<script setup>
import { computed, ref } from 'vue'
import QuestionnairePreviewContent from '@/components/feedback/QuestionnairePreviewContent.vue'
import { SELF_RELATION_CODE } from '@/utils/publicationConfig'

const props = defineProps({ config: { type: Object, required: true }, canEditQuestionnaire: Boolean, canManage: Boolean })
const emit = defineEmits(['edit'])
const activeTab = ref('questionnaire')
const questionnaire = computed(() => props.config.questionnaire)
const questions = computed(() => questionnaire.value?.pages.flatMap(page => page.questions) || [])
const questionLabels = computed(() => new Map(questions.value.map((question, index) => [question.questionCode, `${index + 1}. ${question.title}`])))
const people = computed(() => new Map([...props.config.configuredParticipants, ...props.config.targets].map(person => [person.userId, person])))
const enabledRelations = computed(() => props.config.relations.filter(item => item.isEnabled))
function personName(id) { const person = people.value.get(id); return person?.nickName || person?.userName || `用户${id}` }
function evaluatorNames(target, relation) {
  if (relation === SELF_RELATION_CODE) return `${personName(target)}（本人，自动添加）`
  const ids = props.config.evaluatorSelections.find(item => item.targetUserId === target && item.relationCode === relation)?.evaluatorUserIds || []
  return ids.length ? ids.map(personName).join('、') : '未分配'
}
</script>

<template>
  <el-tabs v-model="activeTab" type="border-card" class="configuration-review">
    <el-tab-pane label="问卷预览" name="questionnaire">
      <div class="review-actions"><span>核对完整题目、选项与说明，可试填。</span><el-button v-if="canEditQuestionnaire" link type="primary" @click="emit('edit', 0)">返回修改问卷</el-button></div>
      <div v-if="questionnaire" class="questionnaire-review"><QuestionnairePreviewContent :draft="questionnaire" :show-editing-indicator="false" /></div>
      <el-alert v-else title="问卷预览暂不可用，请重新加载后核对。" type="warning" :closable="false" />
    </el-tab-pane>
    <el-tab-pane label="指标与权重及绑定题目" name="indicators">
      <div class="review-actions"><span>核对每个指标的占比和绑定题目。</span><el-button v-if="canEditQuestionnaire" link type="primary" @click="emit('edit', 1)">返回修改指标与权重</el-button></div>
      <el-table :data="questionnaire?.indicators || []" size="small" empty-text="暂无指标预览">
        <el-table-column prop="indicatorName" label="指标名称" min-width="140" />
        <el-table-column label="权重" width="90"><template #default="{ row }">{{ Number(row.weight) }}%</template></el-table-column>
        <el-table-column prop="description" label="指标说明" min-width="160" />
        <el-table-column label="绑定计分题" min-width="300"><template #default="{ row }"><div v-for="code in row.questionCodes" :key="code">{{ questionLabels.get(code) || '题目不存在，请返回检查' }}</div></template></el-table-column>
      </el-table>
    </el-tab-pane>
    <el-tab-pane label="评价关系与计分占比" name="relations">
      <div class="review-actions"><span>自评自动添加；仅自评时按自评计分，有他评时自评单独展示。</span><el-button v-if="canManage" link type="primary" @click="emit('edit', 3)">返回修改评价关系</el-button></div>
      <el-table :data="config.relations" size="small">
        <el-table-column prop="relationName" label="评价关系" />
        <el-table-column label="启用评价"><template #default="{ row }">{{ row.isEnabled ? '已启用' : '未启用' }}</template></el-table-column>
        <el-table-column label="计分方式"><template #default="{ row }">{{ row.relationCode === SELF_RELATION_CODE ? '仅自评时计分' : row.isEnabled && row.participatesInScore ? '计入总分' : '不计入总分' }}</template></el-table-column>
        <el-table-column label="占比"><template #default="{ row }">{{ row.relationCode === SELF_RELATION_CODE ? '—' : `${Number(row.weight)}%` }}</template></el-table-column>
      </el-table>
    </el-tab-pane>
    <el-tab-pane label="被评价人与评价人安排" name="people">
      <div class="review-actions"><span>逐人核对各关系的评价人名单。</span><div><el-button v-if="canManage" link type="primary" @click="emit('edit', 2)">返回修改被评价人</el-button><el-button v-if="canManage" link type="primary" @click="emit('edit', 4)">返回修改评价人安排</el-button></div></div>
      <el-table :data="config.targets" size="small">
        <el-table-column label="被评价人" width="160"><template #default="{ row }">{{ personName(row.userId) }}<div>{{ row.deptName }}</div></template></el-table-column>
        <el-table-column label="评价人名单" min-width="320"><template #default="{ row }"><div v-for="relation in enabledRelations" :key="relation.relationCode" class="review-assignment"><strong>{{ relation.relationName }}：</strong>{{ evaluatorNames(row.userId, relation.relationCode) }}</div></template></el-table-column>
      </el-table>
    </el-tab-pane>
  </el-tabs>
</template>

<style scoped>
.configuration-review { margin-top: 20px; }
.configuration-review :deep(> .el-tabs__content) { height: clamp(320px, 55dvh, 620px); padding: 0; overflow: hidden; }
.configuration-review :deep(> .el-tabs__content > .el-tab-pane) { height: 100%; box-sizing: border-box; padding: 15px; overflow: auto; scrollbar-gutter: stable; overscroll-behavior: contain; }
.review-actions { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; margin: 8px 0 16px; color: var(--el-text-color-secondary); }
.questionnaire-review { border: 1px solid var(--el-border-color); padding: 20px; background: var(--el-fill-color-light); }
.review-assignment { padding: 6px 0; }
</style>
