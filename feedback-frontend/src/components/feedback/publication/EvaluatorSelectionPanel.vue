<script setup>
import { computed, ref, watchEffect } from 'vue'

import { SELF_RELATION_CODE } from '@/utils/publicationConfig'

const props = defineProps({
  summaries: { type: Array, default: () => [] },
  assignmentIssues: { type: Array, default: () => [] },
  targets: { type: Array, default: () => [] },
  relations: { type: Array, default: () => [] },
  selections: { type: Array, default: () => [] },
  participants: { type: Array, default: () => [] },
  candidateRows: { type: Array, default: () => [] },
  candidateTotal: { type: Number, default: 0 },
  candidatePageNum: { type: Number, default: 1 },
  candidatePageSize: { type: Number, default: 10 },
  loading: Boolean,
  editable: Boolean
})
const emit = defineEmits(['search', 'page-change', 'set-evaluators'])
const targetUserId = ref(null)
const relationCode = ref('')
const keyword = ref('')
const contextForm = ref(null)
const targetName = computed(() => personName(props.targets.find(item => item.userId === targetUserId.value)))
const relationName = computed(() => props.relations.find(item => item.relationCode === relationCode.value)?.relationName || '')

const selectableRelations = computed(() =>
  props.relations.filter(item => item.isEnabled && item.relationCode !== SELF_RELATION_CODE)
)
const selectionByTarget = computed(() => {
  const result = new Map()
  for (const selection of props.selections) {
    if (!result.has(selection.targetUserId)) result.set(selection.targetUserId, new Map())
    result.get(selection.targetUserId).set(selection.relationCode, selection.evaluatorUserIds)
  }
  return result
})
const selectedIds = computed(() => evaluatorIds(targetUserId.value, relationCode.value))
const participantById = computed(() => new Map(props.participants.map(item => [item.userId, item])))
const selectedParticipants = computed(() => selectedIds.value.map(evaluator))
const assignmentRows = computed(() => props.summaries.map(target => ({
  ...target,
  groups: selectableRelations.value.map(relation => ({
    ...relation,
    people: evaluatorIds(target.userId, relation.relationCode).map(evaluator)
  }))
})))

function evaluatorIds(target, relation) {
  return selectionByTarget.value.get(target)?.get(relation) || []
}

function evaluator(userId) {
  const person = participantById.value.get(userId) || { userId, available: false }
  return { ...person, nickName: personName(person) }
}

function personName(person) {
  return person?.nickName || person?.userName || (person?.userId ? `用户${person.userId}` : '')
}

function personDescription(person) {
  return `${personName(person)} · ${person.userName || '账号未知'} · ${person.deptName || '未分配部门'}`
}

watchEffect(() => {
  if (!props.targets.some(item => item.userId === targetUserId.value)) {
    targetUserId.value = props.targets[0]?.userId || null
  }
  if (!selectableRelations.value.some(item => item.relationCode === relationCode.value)) {
    relationCode.value = selectableRelations.value[0]?.relationCode || ''
  }
})

function addEvaluator(userId) {
  if (!targetUserId.value || !relationCode.value || selectedIds.value.includes(userId)) return
  emit('set-evaluators', targetUserId.value, relationCode.value, [...selectedIds.value, userId])
}

function removeEvaluator(userId) {
  emit(
    'set-evaluators',
    targetUserId.value,
    relationCode.value,
    selectedIds.value.filter(item => item !== userId)
  )
}

function search(event) {
  // 输入法确认选词时不查询；普通回车需在按下时阻止表单默认提交。
  if (event?.isComposing || event?.keyCode === 229) return
  event?.preventDefault()
  if (event?.repeat || props.loading) return
  emit('search', keyword.value.trim())
}

function locate({ targetUserId: target, relationCode: relation } = {}) {
  if (target) targetUserId.value = target
  if (relation) relationCode.value = relation
  contextForm.value?.$el?.scrollIntoView?.({ block: 'center' })
}
defineExpose({ locate })
</script>

<template>
  <section class="evaluator-panel">
    <div class="section-heading">
      <div>
        <h2>3. 谁来评价</h2>
        <p>下方按关系列出已选评价人，点击关系可切换配置。未分配他评的员工将仅进行自评。</p>
      </div>
    </div>

    <div v-if="assignmentIssues.length" class="assignment-issues" role="status">
      <strong>还需完成 {{ assignmentIssues.length }} 项</strong>
      <div v-for="issue in assignmentIssues" :key="issue.message">
        <span>{{ issue.message }}</span>
        <el-button size="small" type="primary" link @click="locate(issue)">去配置</el-button>
      </div>
    </div>
    <el-table :data="assignmentRows" row-key="userId" :max-height="260" size="small" class="assignment-summary">
      <el-table-column label="被评价人" width="140">
        <template #default="{ row }"><strong>{{ personName(row) }}</strong></template>
      </el-table-column>
      <el-table-column label="评价安排 · 点击关系切换" min-width="360">
        <template #default="{ row }">
          <div class="assignment-groups">
            <div v-for="group in row.groups" :key="group.relationCode" class="assignment-group" :class="{ 'is-current': row.userId === targetUserId && group.relationCode === relationCode }">
              <el-button
                size="small" link type="primary" class="group-switch"
                :aria-label="`${editable ? '配置' : '查看'}${personName(row)}的${group.relationName}评价人`"
                :aria-pressed="row.userId === targetUserId && group.relationCode === relationCode"
                @click="locate({ targetUserId: row.userId, relationCode: group.relationCode })"
              >{{ group.relationName }}<span class="group-count">{{ group.people.length }} 人</span></el-button>
              <div class="group-members">
                <el-tag v-for="person in group.people" :key="person.userId" size="small" :type="person.available ? 'info' : 'danger'" :title="personDescription(person)">
                  {{ personName(person) }}{{ person.available ? '' : '（失效）' }}
                </el-tag>
                <span v-if="!group.people.length" class="unassigned-label">未分配</span>
              </div>
            </div>
            <span class="self-note">自评：本人（自动添加）</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="125">
        <template #default="{ row }"><el-tag size="small" :type="row.missingScoring ? 'warning' : row.hasOthers ? 'success' : 'info'">{{ row.missingScoring ? '待补计分评价' : row.hasOthers ? '已分配' : '仅自评' }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" width="90">
        <template #default="{ row }"><el-button link type="primary" @click="locate({ targetUserId: row.userId })">{{ editable ? '配置' : '查看' }}</el-button></template>
      </el-table-column>
    </el-table>

    <el-form ref="contextForm" inline :model="{ targetUserId, relationCode }" class="context-form">
      <el-form-item label="被评价人">
        <el-select v-model="targetUserId" placeholder="选择被评价人" style="width: 220px">
          <el-option
            v-for="item in targets"
            :key="item.userId"
            :label="personName(item)"
            :value="item.userId"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="评价关系" class="relation-picker-item">
        <el-radio-group v-model="relationCode" class="relation-picker" size="small" aria-label="评价关系">
          <el-radio-button
            v-for="item in selectableRelations"
            :key="item.relationCode"
            :value="item.relationCode"
          >{{ item.relationName }}<span class="relation-count">{{ evaluatorIds(targetUserId, item.relationCode).length }} 人</span></el-radio-button>
        </el-radio-group>
      </el-form-item>
    </el-form>
    <p v-if="targetName && relationName" class="assignment-context" aria-live="polite">正在为 <strong>{{ targetName }}</strong> 选择 <strong>{{ relationName }}</strong> 评价人<span>已选 {{ selectedParticipants.length }} 人</span></p>

    <el-empty
      v-if="!targets.length || !selectableRelations.length"
      description="请先选择被评价人，并至少启用一种非自评关系"
      :image-size="84"
    />
    <template v-else>
      <el-form inline :model="{ keyword }" class="participant-filter">
        <el-form-item label="人员搜索">
          <el-input
            v-model="keyword"
            clearable
            placeholder="输入评价人账号或姓名"
            @keydown.enter="search"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="search">查询</el-button>
        </el-form-item>
      </el-form>

      <div class="dual-list">
        <div class="list-column">
          <strong>可选评价人</strong>
          <el-table v-loading="loading" :data="candidateRows" :max-height="320" size="small">
            <el-table-column prop="nickName" label="姓名" min-width="110" />
            <el-table-column prop="userName" label="账号" min-width="110" />
            <el-table-column prop="deptName" label="部门" min-width="120">
              <template #default="{ row }">{{ row.deptName || '未分配部门' }}</template>
            </el-table-column>
            <el-table-column v-if="editable" label="操作" width="76" fixed="right">
              <template #default="{ row }">
                <el-button
                  type="primary"
                  link
                  :disabled="row.userId === targetUserId || selectedIds.includes(row.userId)"
                  @click="addEvaluator(row.userId)"
                >
                  {{ row.userId === targetUserId ? '本人' : selectedIds.includes(row.userId) ? '已选' : '添加' }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination
            class="mini-pagination"
            size="small"
            background
            layout="total, prev, pager, next"
            :total="candidateTotal"
            :page-size="candidatePageSize"
            :current-page="candidatePageNum"
            @current-change="emit('page-change', $event)"
          />
        </div>

        <div class="list-column selected-column">
          <strong>已选{{ relationName }}评价人（{{ selectedParticipants.length }}）</strong>
          <el-table :data="selectedParticipants" :max-height="320" size="small" :empty-text="`从左侧为${targetName}添加${relationName}评价人`">
            <el-table-column prop="nickName" label="姓名" min-width="120" />
            <el-table-column prop="deptName" label="部门" min-width="120">
              <template #default="{ row }">{{ row.deptName || '未分配部门' }}</template>
            </el-table-column>
            <el-table-column label="状态" width="76">
              <template #default="{ row }">
                <el-tag :type="row.available ? 'success' : 'danger'" size="small">
                  {{ row.available ? '可用' : '失效' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column v-if="editable" label="操作" width="76" fixed="right">
              <template #default="{ row }">
                <el-button type="danger" link @click="removeEvaluator(row.userId)">移除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
    </template>
  </section>
</template>

<style scoped>
.evaluator-panel { display: grid; grid-template-columns: minmax(0, 1fr); gap: 14px; }
.section-heading h2, .section-heading p { margin: 0; }
.section-heading h2 { font-size: 18px; }
.section-heading p { margin-top: 6px; color: var(--fb-text-muted, #64748b); font-size: 13px; }
.context-form, .participant-filter { margin-bottom: -8px; }
.context-form { display: flex; flex-wrap: wrap; gap: 8px 20px; }
.context-form:deep(.el-form-item) { margin: 0 0 8px; }
.relation-picker-item { flex: 1; min-width: 0; }
.relation-picker { display: flex; flex-wrap: wrap; gap: 4px; }
.relation-picker:deep(.el-radio-button__inner) { border: 1px solid var(--el-border-color); border-radius: 4px; box-shadow: none; }
.relation-picker:deep(.is-active .el-radio-button__inner) { border-color: var(--el-color-primary); }
.relation-count { margin-left: 8px; font-size: 12px; opacity: .85; }
.assignment-groups { display: grid; gap: 4px; padding: 4px 0; }
.assignment-group { display: flex; align-items: flex-start; gap: 10px; padding: 4px 8px; border: 1px solid transparent; border-radius: 4px; }
.assignment-group.is-current { border-color: var(--el-color-primary-light-7); background: var(--el-color-primary-light-9); }
.group-switch { flex: 0 0 104px; justify-content: flex-start; height: auto; min-height: 24px; white-space: normal; text-align: left; }
.group-switch:deep(span) { flex-wrap: wrap; }
.group-count { margin-left: 6px; color: var(--el-text-color-secondary); font-weight: normal; }
.group-members { display: flex; flex: 1; flex-wrap: wrap; min-width: 0; gap: 4px; padding-top: 2px; }
.group-members .el-tag { max-width: 100%; }
.group-members:deep(.el-tag__content) { overflow: hidden; text-overflow: ellipsis; }
.self-note, .unassigned-label { color: var(--el-text-color-secondary); font-size: 12px; }
.self-note { padding-left: 8px; }
.assignment-context { margin: 0; padding: 10px 14px; color: var(--fb-primary-text, #337ecc); background: var(--fb-primary-bg, #ecf5ff); border-radius: 6px; font-size: 14px; }
.assignment-context > span { margin-left: 16px; font-size: 12px; }
.assignment-issues { display: grid; gap: 6px; padding: 12px; border-radius: 6px; background: var(--fb-warning-bg, #fdf6ec); font-size: 13px; color: var(--fb-warning-text, #b26a16); }
.assignment-issues > div { display: flex; justify-content: space-between; gap: 12px; }
.dual-list { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 18px; }
.list-column { min-width: 0; padding: 14px; border: 1px solid var(--fb-border, #e5e7eb); border-radius: 8px; }
.list-column > strong { display: block; margin-bottom: 10px; }
.selected-column { background: var(--fb-surface-muted, #f8fafc); }
.mini-pagination { justify-content: flex-end; margin-top: 14px; }
@media (max-width: 980px) { .dual-list { grid-template-columns: 1fr; } }
</style>
