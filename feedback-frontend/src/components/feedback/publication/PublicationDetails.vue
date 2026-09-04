<script setup>
import { computed, nextTick, ref } from 'vue'
import { useRouter } from 'vue-router'

import RichTextEditor from '@/components/feedback/RichTextEditor.vue'
import { getQuestionTypeDefinition } from '@/components/feedback/questions/questionTypeRegistry'
import { usePermissionStore } from '@/stores/permission'
import { formatDateTime } from '@/utils/displayFormat'
import { normalizeDecimal } from '@/utils/fixedDecimal'
import { SELF_RELATION_CODE } from '@/utils/publicationConfig'

const props = defineProps({ config: { type: Object, required: true } })
const router = useRouter()
const permissions = usePermissionStore()
const activeTab = ref('overview')
const pageNumber = ref(1)
const highlightedQuestion = ref('')
const questionList = ref(null)
const keyword = ref('')
const searchText = ref('')
const peoplePage = ref(1)
const details = computed(() => props.config.frozenDetails)
const questionnaire = computed(() => details.value?.questionnaire)
const pages = computed(() => questionnaire.value?.pages || [])
const currentPage = computed(() => pages.value[pageNumber.value - 1])
const questions = computed(() => pages.value.flatMap((page, pageIndex) => page.questions.map(question => ({ ...question, pageIndex }))))
const questionByCode = computed(() => new Map(questions.value.map((question, index) => [question.questionCode, { ...question, number: index + 1 }])))
const participants = computed(() => new Map(props.config.configuredParticipants.map(person => [person.userId, person])))
const enabledRelations = computed(() => props.config.relations.filter(relation => relation.isEnabled))
const scoredRelations = computed(() => enabledRelations.value.filter(relation => relation.relationCode !== SELF_RELATION_CODE && relation.participatesInScore))
const onlySelf = computed(() => props.config.targets.every(target => target.onlySelfEvaluation))
const scoreSummary = computed(() => onlySelf.value ? '本轮仅自评，按每人的自评结果计分。' : scoredRelations.value.map(relation => `${relation.relationName}占 ${decimal(relation.weight)}%`).join('，'))
const selectionsByTarget = computed(() => {
  const result = new Map()
  for (const selection of props.config.evaluatorSelections) {
    if (!result.has(selection.targetUserId)) result.set(selection.targetUserId, new Map())
    result.get(selection.targetUserId).set(selection.relationCode, selection.evaluatorUserIds)
  }
  return result
})
const summaries = computed(() => new Map(props.config.preview.targetSummaries.map(row => [row.targetUserId, row])))
const targetRows = computed(() => props.config.targets.map(target => ({
  ...target,
  assignmentCount: summaries.value.get(target.userId)?.assignmentCount ?? 0,
  groups: enabledRelations.value.map(relation => ({
    ...relation,
    people: (selectionsByTarget.value.get(target.userId)?.get(relation.relationCode) || []).map(userId => participants.value.get(userId) || { userId })
  }))
})))
const filteredTargets = computed(() => targetRows.value.filter(target => {
  const text = [name(target), target.deptName, ...target.groups.flatMap(group => group.people.flatMap(person => [name(person), person.deptName]))].join(' ').toLowerCase()
  return text.includes(searchText.value.toLowerCase())
}))
const visibleTargets = computed(() => filteredTargets.value.slice((peoplePage.value - 1) * 10, peoplePage.value * 10))

function name(person) { return person.nickName || person.userName || `用户${person.userId}` }
function decimal(value) { return normalizeDecimal(value ?? 0).replace(/\.?0+$/, '') || '0' }
function questionType(question) { return getQuestionTypeDefinition(question.questionType)?.label || '题目' }
function questionScore(question) { return decimal(getQuestionTypeDefinition(question.questionType)?.calculateMaxScore(question) ?? 0) }
function search(event) {
  if (event?.isComposing || event?.keyCode === 229) return
  event?.preventDefault()
  if (event?.repeat) return
  searchText.value = keyword.value.trim()
  peoplePage.value = 1
}
async function locateQuestion(code) {
  const question = questionByCode.value.get(code)
  if (!question) return
  pageNumber.value = question.pageIndex + 1
  highlightedQuestion.value = code
  await nextTick()
  const card = [...(questionList.value?.querySelectorAll('[data-question-code]') || [])].find(element => element.dataset.questionCode === code)
  card?.focus({ preventScroll: true })
  card?.scrollIntoView?.({ block: 'center' })
}
</script>

<template>
  <section class="publication-details">
    <div class="published-banner">
      <div><el-tag :type="config.projectStatus === 'COMPLETED' ? 'info' : 'success'">{{ config.projectStatus === 'COMPLETED' ? '已完成' : '进行阶段' }}</el-tag><span>已发布 · 以下配置已锁定，供查阅和核对。</span></div>
      <el-button v-if="permissions.hasPermission('feedback:progress:view')" type="primary" @click="router.push(`/hr/projects/${config.projectId}/progress`)">查看评价进度</el-button>
    </div>
    <el-tabs v-model="activeTab" class="detail-tabs">
      <el-tab-pane label="发布概要" name="overview">
        <div class="overview-counts">
          <el-statistic title="被评价人数" :value="config.preview.targetCount" />
          <div><el-statistic title="评价人数" :value="config.preview.evaluatorCount" /><p class="muted">去重人数，包含自评人员</p></div>
          <el-statistic title="已生成任务" :value="config.preview.assignmentCount" />
        </div>
        <el-descriptions v-if="details" :column="1" border class="publication-metadata">
          <el-descriptions-item label="发布时间">{{ formatDateTime(details.publishedTime) }}</el-descriptions-item>
          <el-descriptions-item label="发布人账号">{{ details.publishedByName }}</el-descriptions-item>
          <el-descriptions-item label="发布问卷">{{ questionnaire.title }} · 第 {{ details.versionNo }} 版 · {{ pages.length }} 页 / {{ questions.length }} 题</el-descriptions-item>
          <el-descriptions-item label="评价指标">{{ questionnaire.indicators.length }} 项 <el-button link type="primary" @click="activeTab = 'questionnaire'">查看问卷与指标</el-button></el-descriptions-item>
          <el-descriptions-item label="计分方式">{{ scoreSummary }} <el-button link type="primary" @click="activeTab = 'rules'">查看评价规则</el-button></el-descriptions-item>
        </el-descriptions>
        <el-alert v-else title="发布详情暂未加载完整，请刷新重试；下方仍可核对已保存的人员安排。" type="warning" :closable="false" show-icon />
        <div class="section-title"><h2>人员与任务</h2><el-button link type="primary" @click="activeTab = 'people'">查看具体评价人</el-button></div>
        <el-table :data="config.preview.targetSummaries" size="small" max-height="360">
          <el-table-column label="被评价人" min-width="180"><template #default="{ row }">{{ name(config.targets.find(target => target.userId === row.targetUserId) || { userId: row.targetUserId }) }}</template></el-table-column>
          <el-table-column prop="selfCount" label="自评任务" width="110" />
          <el-table-column prop="nonSelfCount" label="他评任务" width="110" />
          <el-table-column prop="assignmentCount" label="任务合计" width="110" />
        </el-table>
        <p class="muted">这里展示发布时的任务安排；填写和提交情况请在“评价进度”中查看。</p>
      </el-tab-pane>

      <el-tab-pane label="问卷与指标" name="questionnaire" lazy>
        <el-empty v-if="!questionnaire" description="冻结问卷详情暂不可用，请刷新重试" />
        <div v-else class="questionnaire-layout">
          <div ref="questionList" class="frozen-questionnaire">
            <h2>{{ questionnaire.title }}</h2>
            <RichTextEditor v-if="questionnaire.descriptionDoc" :model-value="questionnaire.descriptionDoc" readonly />
            <p v-else-if="questionnaire.description" class="preserve-text">{{ questionnaire.description }}</p>
            <article v-for="question in currentPage?.questions || []" :key="question.questionCode" tabindex="-1" :data-question-code="question.questionCode" :class="['frozen-question', { highlighted: highlightedQuestion === question.questionCode }]">
              <div class="question-meta"><el-tag size="small">{{ questionType(question) }}</el-tag><span>{{ question.isRequired ? '必答' : '选答' }}</span><span>{{ question.isScored ? `计分 · 满分 ${questionScore(question)} 分` : '不计分' }}</span></div>
              <h3>第 {{ questionByCode.get(question.questionCode).number }} 题 · {{ question.title }}</h3>
              <p v-if="question.description" class="muted preserve-text">{{ question.description }}</p>
              <ul v-if="question.questionType === 'SINGLE_CHOICE'" class="frozen-options"><li v-for="option in question.options" :key="option.optionCode"><span>{{ option.optionLabel }}<small v-if="option.requiresReason">（选择后需说明原因）</small></span><span v-if="question.isScored">{{ decimal(option.score) }} 分</span></li></ul>
              <p v-else-if="question.questionType === 'TEXT'" class="muted">文字反馈，最多 {{ question.config.maxLength || 1000 }} 字。</p>
              <p v-else class="muted">评分范围：{{ decimal(question.minScore) }}～{{ decimal(question.maxScore) }} 分<span v-if="question.questionType === 'NUMERIC_INPUT'">，允许 {{ question.decimalPlaces }} 位小数</span><span v-if="question.questionType === 'SLIDER'">，每次增减 {{ decimal(question.config.step) }} 分</span><span v-if="question.config.defaultValue != null">，默认 {{ decimal(question.config.defaultValue) }} 分</span>。</p>
            </article>
            <div class="page-navigation"><strong>{{ currentPage?.pageTitle }} · 第 {{ pageNumber }} / {{ pages.length }} 页</strong><el-pagination v-model:current-page="pageNumber" :page-size="1" :total="pages.length" :pager-count="5" layout="prev, pager, next" size="small" /></div>
          </div>
          <aside class="frozen-indicators">
            <h2>评价指标 · {{ questionnaire.indicators.length }} 项</h2>
            <p class="muted">指标决定评价哪些方面、各占总分多少。点击绑定题目可定位。</p>
            <article v-for="indicator in questionnaire.indicators" :key="indicator.indicatorCode" class="frozen-indicator">
              <div class="section-title"><strong>{{ indicator.indicatorName }}</strong><el-tag>{{ decimal(indicator.weight) }}%</el-tag></div>
              <p v-if="indicator.description" class="muted preserve-text">{{ indicator.description }}</p>
              <div class="indicator-questions"><el-button v-for="code in indicator.questionCodes" :key="code" text type="primary" @click="locateQuestion(code)">第 {{ questionByCode.get(code)?.number }} 题 · {{ questionByCode.get(code)?.title || '题目不可用' }}</el-button></div>
            </article>
          </aside>
        </div>
      </el-tab-pane>

      <el-tab-pane label="评价规则" name="rules" lazy>
        <h2>本轮计分方式</h2><p class="score-summary">{{ scoreSummary }}</p>
        <el-table :data="enabledRelations" size="small">
          <el-table-column prop="relationName" label="评价关系" min-width="160" />
          <el-table-column label="计分用途" min-width="180"><template #default="{ row }">{{ row.relationCode === SELF_RELATION_CODE ? '自评单独展示' : row.participatesInScore ? '计入他评总分' : '仅供参考' }}</template></el-table-column>
          <el-table-column label="占比" width="170"><template #default="{ row }">{{ row.relationCode === SELF_RELATION_CODE ? '仅自评时计分' : row.participatesInScore ? `${decimal(row.weight)}%` : '不计入总分' }}</template></el-table-column>
        </el-table>
        <div class="rule-explanation"><p>同类多人评价先取平均，再按关系占比合并，最后按评价指标占比汇总。</p><p>有他评时，自评单独展示；发布时未分配他评的员工按自评结果计分。</p><p>只统计已提交答卷。同一关系有人未提交时，取已提交评价的平均分；某类关系全部未提交时，其占比按比例分配给有有效答卷的计分关系。全部计分他评缺失时显示“数据不足”，不用自评补足。</p><p>已提交答卷中的可选计分题未答时不增加得分，指标满分不减少；报告会显示完成率和缺失情况。</p></div>
        <p class="muted">未启用的关系不参与本轮评价。问卷题目及评价指标占比见“问卷与指标”。</p>
      </el-tab-pane>

      <el-tab-pane label="人员安排" name="people" lazy>
        <div class="section-title"><h2>谁评价谁</h2><span class="muted">姓名、部门为发布时信息</span></div>
        <el-form inline :model="{ keyword }" class="people-filter"><el-form-item label="人员搜索"><el-input v-model="keyword" clearable placeholder="被评价人、评价人姓名或部门" @keydown.enter="search" /></el-form-item><el-form-item><el-button type="primary" @click="search">查询</el-button></el-form-item></el-form>
        <el-table :data="visibleTargets" row-key="userId" size="small" empty-text="没有匹配的人员安排">
          <el-table-column label="被评价人" min-width="170"><template #default="{ row }"><strong>{{ name(row) }}</strong><p class="muted">{{ row.deptName || '未分配部门' }}</p></template></el-table-column>
          <el-table-column label="已发布的评价安排" min-width="380"><template #default="{ row }"><div v-for="group in row.groups" :key="group.relationCode" class="frozen-group"><strong>{{ group.relationName }}</strong><div><template v-if="group.relationCode === SELF_RELATION_CODE">本人 · {{ name(row) }}</template><template v-else-if="group.people.length"><el-tag v-for="person in group.people" :key="person.userId" type="info" :title="`${name(person)} · ${person.deptName || '未分配部门'}`">{{ name(person) }}</el-tag><span class="muted">{{ group.people.length }} 人</span></template><span v-else class="muted">未分配</span></div></div></template></el-table-column>
          <el-table-column label="评价方式" width="140"><template #default="{ row }">{{ row.onlySelfEvaluation ? '仅自评' : '自评 + 他评' }}</template></el-table-column>
          <el-table-column prop="assignmentCount" label="任务数" width="90" />
        </el-table>
        <el-pagination v-model:current-page="peoplePage" :page-size="10" :total="filteredTargets.length" :pager-count="5" layout="total, prev, pager, next" class="people-pagination" />
      </el-tab-pane>
    </el-tabs>
  </section>
</template>

<style scoped>
.publication-details { min-width: 0; }
.published-banner, .published-banner > div, .section-title, .page-navigation { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.published-banner { margin-bottom: 14px; padding: 12px 16px; background: var(--fb-success-bg, #f0f9eb); border-radius: 6px; font-size: 13px; }
.published-banner > div { justify-content: flex-start; flex-wrap: wrap; }
.detail-tabs { padding: 8px 20px 20px; background: var(--fb-surface, #fff); border: 1px solid var(--fb-border, #e4e7ed); border-radius: 8px; }
.detail-tabs:deep(.el-tabs__content) { overflow: hidden; }
.overview-counts { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; padding: 16px 0 20px; }
.publication-metadata { margin-bottom: 24px; }
.section-title { margin: 12px 0; }
h2 { margin: 12px 0; font-size: 17px; }
.muted { margin: 6px 0; color: var(--fb-text-muted, #64748b); font-size: 13px; line-height: 1.7; }
.preserve-text { white-space: pre-wrap; overflow-wrap: anywhere; }
.questionnaire-layout { display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: 24px; }
.frozen-questionnaire, .frozen-indicators { min-width: 0; }
.frozen-questionnaire > h2 { text-align: center; font-size: 20px; overflow-wrap: anywhere; }
.page-navigation { flex-wrap: wrap; padding: 16px 0; border-top: 1px solid var(--fb-border, #e5e7eb); font-size: 13px; }
.frozen-question { padding: 16px; border: 1px solid var(--fb-border, #e5e7eb); border-radius: 6px; margin: 14px 0; scroll-margin-top: 80px; }
.frozen-question.highlighted, .frozen-question:focus-visible { outline: 2px solid #409eff; outline-offset: 1px; }
.frozen-question h3 { font-size: 15px; margin: 10px 0; line-height: 1.7; white-space: pre-wrap; overflow-wrap: anywhere; }
.question-meta { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; font-size: 12px; color: var(--fb-text-muted, #64748b); }
.frozen-options { list-style: none; padding: 0; margin: 0; }
.frozen-options li { display: flex; justify-content: space-between; gap: 16px; padding: 8px 0; border-bottom: 1px solid var(--fb-border, #f1f5f9); font-size: 14px; }
.frozen-options li > span:first-child { overflow-wrap: anywhere; min-width: 0; }
.frozen-options li > span + span { flex-shrink: 0; }
.frozen-options small { color: var(--fb-text-muted, #64748b); }
.frozen-indicator { padding: 12px; margin-top: 12px; border: 1px solid var(--fb-border, #e5e7eb); border-radius: 6px; }
.frozen-indicator .section-title { margin: 0 0 8px; }
.frozen-indicator strong { overflow-wrap: anywhere; min-width: 0; }
.indicator-questions { display: grid; max-height: 260px; overflow-y: auto; }
.indicator-questions .el-button { margin: 0; height: auto; padding: 6px 4px; justify-content: flex-start; white-space: normal; text-align: left; }
.indicator-questions:deep(span) { overflow-wrap: anywhere; min-width: 0; }
.score-summary { padding: 12px 16px; background: var(--fb-primary-bg, #ecf5ff); color: var(--fb-primary-text, #337ecc); border-radius: 6px; }
.rule-explanation { line-height: 1.8; color: var(--fb-text-regular, #475569); font-size: 14px; }
.people-filter { margin-top: 16px; }
.people-filter .el-input { width: 250px; }
.frozen-group { display: flex; gap: 16px; padding: 6px 0; }
.frozen-group > strong { flex: 0 0 88px; overflow-wrap: anywhere; }
.frozen-group > div { display: flex; align-items: center; flex-wrap: wrap; min-width: 0; gap: 6px; }
.frozen-group .el-tag { height: auto; padding: 3px 8px; color: var(--fb-text-regular, #334155); background: var(--fb-surface-muted, #f5f7fa); border-color: var(--fb-border, #dbe4ef); font-size: 13px; line-height: 1.5; white-space: normal; overflow-wrap: anywhere; }
.people-pagination { margin-top: 16px; justify-content: flex-end; }
@media (max-width: 1100px) { .questionnaire-layout { grid-template-columns: minmax(0, 1fr); } }
@media (max-width: 760px) { .detail-tabs { padding: 8px 12px 12px; } .published-banner { align-items: flex-start; flex-wrap: wrap; } }
</style>
