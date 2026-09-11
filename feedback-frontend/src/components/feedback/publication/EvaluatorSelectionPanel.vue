<script setup>
import { computed, ref, watch, watchEffect } from 'vue'

import TargetSelectorPanel from './TargetSelectorPanel.vue'

import { SELF_RELATION_CODE } from '@/utils/publicationConfig'

const props = defineProps({
  loadDepartments: { type: Function, required: true },
  loadPeople: { type: Function, required: true },
  summaries: { type: Array, default: () => [] },
  assignmentIssues: { type: Array, default: () => [] },
  targets: { type: Array, default: () => [] },
  relations: { type: Array, default: () => [] },
  selections: { type: Array, default: () => [] },
  participants: { type: Array, default: () => [] },
  active: { type: Boolean, default: true },
  editable: Boolean
})
const emit = defineEmits(['set-evaluators', 'remember-person'])
const targetUserId = ref(null)
const relationCode = ref('')
const contextModel = computed(() => ({ targetUserId: targetUserId.value, relationCode: relationCode.value }))
const drawerOpen = ref(false)
watch(() => props.active, active => { if (!active) drawerOpen.value = false })
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
let pendingIds = []
watchEffect(() => { pendingIds = [...selectedIds.value] })
const participantById = computed(() => new Map(props.participants.map(item => [item.userId, item])))
const excludedIds = computed(() => [targetUserId.value])
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

function addPerson(person) {
  if (!props.editable || person.userId === targetUserId.value || person.available === false) return
  emit('remember-person', person)
  addEvaluator(person.userId)
}

function addEvaluator(userId) {
  if (!targetUserId.value || !relationCode.value || pendingIds.includes(userId)) return
  pendingIds = [...pendingIds, userId]
  emit('set-evaluators', targetUserId.value, relationCode.value, pendingIds)
}

function removeEvaluator(userId) {
  if (!props.editable) return
  pendingIds = pendingIds.filter(item => item !== userId)
  emit(
    'set-evaluators',
    targetUserId.value,
    relationCode.value,
    pendingIds
  )
}

function locate({ targetUserId: target, relationCode: relation } = {}) {
  if (target) targetUserId.value = target
  if (relation) relationCode.value = relation
  drawerOpen.value = true
}
defineExpose({ locate })
</script>

<template>
  <section class="evaluator-panel">
    <div class="section-heading">
      <div>
        <h2>5. 谁来评价</h2>
        <p>下方按关系列出已选评价人，点击关系可切换配置。每位被评价人都须配齐已启用关系的评价人。</p>
      </div>
    </div>

    <div v-if="assignmentIssues.length" class="assignment-issues" role="status">
      <strong>还需完成 {{ assignmentIssues.length }} 项</strong>
      <div v-for="issue in assignmentIssues" :key="issue.message">
        <span>{{ issue.message }}</span>
        <el-button size="small" type="primary" link @click="locate(issue)">去配置</el-button>
      </div>
    </div>
    <el-table :data="assignmentRows" row-key="userId" size="small" class="assignment-summary">
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
        <template #default="{ row }"><el-tag size="small" :type="row.missingScoring ? 'warning' : row.hasOthers ? 'success' : 'info'">{{ row.missingScoring ? '待补评价人' : row.hasOthers ? '已分配' : '仅自评' }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" width="90">
        <template #default="{ row }"><el-button link type="primary" @click="locate({ targetUserId: row.userId })">{{ editable ? '配置' : '查看' }}</el-button></template>
      </el-table-column>
    </el-table>

    <el-drawer v-model="drawerOpen" :title="`${editable ? '配置' : '查看'}评价人 · ${targetName}`" size="min(1100px, 100vw)" append-to-body destroy-on-close>
      <div class="evaluator-drawer-content">
    <el-form inline :model="contextModel" class="context-form">
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
    <TargetSelectorPanel
      v-else
      :key="`${targetUserId}-${relationCode}`"
      :show-heading="false"
      :selected-label="`已选${relationName}评价人（${selectedParticipants.length}）`"
      :selected-targets="selectedParticipants"
      :excluded-ids="excludedIds"
      :allow-department="selectableRelations.find(item => item.relationCode === relationCode)?.relationType === 'PEER'"
      :can-browse="editable"
      :editable="editable"
      :load-departments="loadDepartments"
      :load-people="loadPeople"
      @add="addPerson"
      @remove="removeEvaluator"
    />
      </div>
      <template #footer>
        <span v-if="editable" class="drawer-save-hint">选择结果已保留在当前配置中，请在页面保存配置。</span>
        <el-button type="primary" @click="drawerOpen = false">完成</el-button>
      </template>
    </el-drawer>
  </section>
</template>

<style scoped>
.evaluator-drawer-content { display: grid; gap: 16px; }
.drawer-save-hint { margin-right: 16px; color: var(--el-text-color-secondary); font-size: 12px; }
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
