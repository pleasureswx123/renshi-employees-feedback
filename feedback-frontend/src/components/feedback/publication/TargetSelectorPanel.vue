<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps({
  selectedTargets: { type: Array, default: () => [] },
  canBrowse: Boolean, editable: Boolean,
  showHeading: { type: Boolean, default: true },
  selectedLabel: { type: String, default: '已选被评价人' },
  excludedIds: { type: Array, default: () => [] },
  allowDepartment: Boolean,
  loadDepartments: { type: Function, required: true },
  loadPeople: { type: Function, required: true }
})
const emit = defineEmits(['add', 'remove'])
const tree = ref(null)
const keyword = ref('')
const searchTerm = ref('')
const selectedKeyword = ref('')
const revision = ref(0)
const loading = ref(false)
const departmentLoading = ref(false)
const error = ref('')
const departments = ref([])
const expandedDepartmentKeys = computed(() => searchTerm.value ? [] : departments.value
  .filter(dept => dept.deptId !== 0 && departments.value.some(child => child.deptId !== 0 && child.parentId === dept.deptId))
  .map(dept => `dept-${dept.deptId}`))
const checkedPeople = ref([])
const checkedSelected = ref([])
const loadingMore = ref(new Set())
const selectedIds = computed(() => new Set(props.selectedTargets.map(person => person.userId)))
const filteredTargets = computed(() => props.selectedTargets.filter(person =>
  `${person.nickName} ${person.userName || ''} ${person.deptName || ''}`.toLowerCase().includes(selectedKeyword.value.trim().toLowerCase())))
const treeProps = {
  label: 'label', isLeaf: data => data.kind !== 'department',
  disabled: data => !props.editable || departmentLoading.value || data.kind !== 'person' || !canSelect(data.person)
}
const canSelect = person => person.available !== false && !props.excludedIds.includes(person.userId) && !selectedIds.value.has(person.userId)
const departmentNode = dept => ({ ...dept, key: `dept-${dept.deptId}`, kind: 'department' })
async function peoplePage(deptId, pageNum, term = '') {
  const params = { pageNum, pageSize: 50 }
  if (term) params.keyword = term
  else if (deptId === 0) params.unassigned = true
  else params.deptId = deptId
  const response = await props.loadPeople(params)
  const nodes = (response.rows || []).map(person => ({ key: `user-${person.userId}`, kind: 'person', label: person.nickName, person }))
  if (pageNum * 50 < Number(response.total || 0)) nodes.push({ key: `more-${deptId ?? 'search'}-${pageNum}`, kind: 'more', label: '加载更多', deptId, pageNum: pageNum + 1, term })
  return nodes
}
async function loadTree(node, resolve, reject) {
  const current = revision.value
  if (!props.canBrowse) return resolve([])
  if (node.level === 0) loading.value = true
  error.value = ''
  try {
    let nodes
    if (node.level === 0) {
      if (searchTerm.value) nodes = await peoplePage(undefined, 1, searchTerm.value)
      else {
        const items = await props.loadDepartments()
        if (current !== revision.value) return resolve([])
        departments.value = items
        nodes = items.filter(dept => dept.deptId === 0 || !items.some(parent => parent.deptId !== 0 && parent.deptId === dept.parentId)).map(departmentNode)
      }
    } else {
      const dept = node.data
      const children = departments.value.filter(child => child.deptId !== 0 && child.parentId === dept.deptId).map(departmentNode)
      nodes = [...children, ...(dept.directCount ? await peoplePage(dept.deptId, 1) : [])]
    }
    if (current !== revision.value) return resolve([])
    resolve(nodes)
  } catch (failure) {
    if (current !== revision.value) return resolve([])
    error.value = failure?.message || '加载失败，请重试'
    if (reject) reject()
    else resolve([])
  } finally {
    if (current === revision.value && node.level === 0) loading.value = false
  }
}
async function loadMore(data, node) {
  if (loadingMore.value.has(data.key) || !props.canBrowse) return
  const current = revision.value
  loadingMore.value.add(data.key)
  error.value = ''
  try {
    const nodes = await peoplePage(data.deptId, data.pageNum, data.term)
    if (current !== revision.value) return
    for (const item of nodes) if (!tree.value.getNode(item.key)) tree.value.append(item, node.parent.level ? node.parent : undefined)
    tree.value.remove(node)
  } catch (failure) {
    if (current === revision.value) error.value = failure?.message || '加载失败，请重试'
  } finally { loadingMore.value.delete(data.key) }
}
function search(event) {
  if (event?.isComposing || event?.keyCode === 229) return
  event?.preventDefault()
  if (event?.repeat || loading.value || !props.canBrowse) return
  searchTerm.value = keyword.value.trim()
  checkedPeople.value = []
  error.value = ''
  revision.value += 1
}
function checkPeople() {
  checkedPeople.value = (tree.value?.getCheckedNodes() || []).filter(node => node.kind === 'person' && canSelect(node.person)).map(node => node.person)
}
function addChecked() {
  if (!props.editable || departmentLoading.value) return
  for (const person of checkedPeople.value) if (!selectedIds.value.has(person.userId)) emit('add', person)
  tree.value?.setCheckedKeys([])
  checkedPeople.value = []
}
async function addDepartment(dept) {
  if (!props.editable || !props.canBrowse || departmentLoading.value) return
  const current = revision.value
  departmentLoading.value = true
  error.value = ''
  try {
    // 按部门逐页读取完整人员集合；包含下级部门，全部成功后才更新选择。
    const ids = new Set([dept.deptId])
    if (dept.deptId !== 0) {
      let changed = true
      while (changed) {
        changed = false
        for (const child of departments.value) {
          if (child.deptId !== 0 && ids.has(child.parentId) && !ids.has(child.deptId)) {
            ids.add(child.deptId)
            changed = true
          }
        }
      }
    }
    const people = new Map()
    for (const deptId of ids) {
      let pageNum = 1
      let total = 0
      do {
        const response = await props.loadPeople({ pageNum, pageSize: 50, ...(deptId === 0 ? { unassigned: true } : { deptId }) })
        if (current !== revision.value || !props.editable) return
        const rows = response.rows || []
        total = Number(response.total || 0)
        if (!rows.length && (pageNum - 1) * 50 < total) throw new Error('部门人员未加载完整，请重试')
        for (const person of rows) if (canSelect(person)) people.set(person.userId, person)
        pageNum += 1
      } while ((pageNum - 1) * 50 < total)
    }
    if (current !== revision.value || !props.editable) return
    for (const person of people.values()) emit('add', person)
  } catch (failure) {
    if (current === revision.value) error.value = failure?.message || '部门人员加载失败，请重试'
  } finally { departmentLoading.value = false }
}
function removeChecked() {
  if (!props.editable || departmentLoading.value) return
  for (const person of checkedSelected.value) if (selectedIds.value.has(person.userId)) emit('remove', person.userId)
  checkedSelected.value = []
}
watch(selectedIds, () => { checkPeople(); tree.value?.setCheckedKeys(checkedPeople.value.map(person => `user-${person.userId}`)) })
watch(() => props.canBrowse, () => { loading.value = false; checkedPeople.value = []; revision.value += 1 })
onBeforeUnmount(() => { revision.value += 1 })
</script>

<template>
  <section :class="showHeading ? 'selector-panel' : 'evaluator-transfer'">
    <div v-if="showHeading" class="section-heading"><div><h2>3. 评价谁</h2><p>展开部门勾选员工，添加到右侧作为本轮被评价人。</p></div><el-tag type="info" size="small">已选 {{ selectedTargets.length }} 人</el-tag></div>
    <div class="target-transfer">
      <div class="list-column source-column">
        <div class="column-heading"><strong>组织与人员</strong><span>已勾选 {{ checkedPeople.length }} 人</span></div>
        <el-form inline size="small" :model="{ keyword }" class="participant-filter">
          <el-form-item label="人员搜索"><el-input v-model="keyword" clearable maxlength="100" placeholder="输入账号或姓名" :disabled="!canBrowse" @keydown.enter="search" @clear="search" /></el-form-item>
          <el-form-item><el-button :loading="loading" :disabled="!canBrowse" @click="search">查询</el-button></el-form-item>
        </el-form>
        <div v-if="error" class="load-error" role="alert">{{ error }} <el-button link type="primary" size="small" @click="search">重新加载</el-button></div>
        <div v-loading="loading" class="tree-scroll">
          <el-tree :key="revision" ref="tree" node-key="key" :props="treeProps" :load="loadTree" :default-expanded-keys="expandedDepartmentKeys" lazy show-checkbox check-strictly empty-text="暂无可选人员" @check="checkPeople">
            <template #default="{ data, node }">
              <span v-if="data.kind === 'department'" class="department-node" :title="data.label">{{ data.label }}<el-button v-if="allowDepartment && editable" link type="primary" size="small" :disabled="departmentLoading" :aria-label="`添加${data.label}全部人员`" @click.stop="addDepartment(data)">添加整部门</el-button></span>
              <el-button v-else-if="data.kind === 'more'" link type="primary" size="small" class="more-node" :loading="loadingMore.has(data.key)" @click.stop="loadMore(data, node)">加载更多</el-button>
              <span v-else class="person-node" :title="`${data.label} · ${data.person.userName || ''} · ${data.person.deptName || '未分配部门'}`"><span>{{ data.label }}</span><small>{{ data.person.deptName || '未分配部门' }}</small><small v-if="selectedIds.has(data.person.userId)">已选</small></span>
            </template>
          </el-tree>
        </div>
        <p class="selection-note">勾选员工后点击添加；搜索留空可返回组织架构。<template v-if="allowDepartment">添加整部门包含下级部门，自动排除本人及已选人员。</template></p>
      </div>
      <div v-if="editable" class="transfer-actions">
        <el-button type="primary" size="small" :loading="departmentLoading" :disabled="!checkedPeople.length || departmentLoading" aria-label="添加选中人员" @click="addChecked">添加 →</el-button>
        <el-button size="small" :disabled="!checkedSelected.length || departmentLoading" aria-label="移除选中人员" @click="removeChecked">← 移除</el-button>
      </div>
      <div class="list-column selected-column">
        <div class="column-heading"><strong>{{ selectedLabel }}</strong><span>{{ selectedTargets.length }} 人</span></div>
        <el-input v-model="selectedKeyword" size="small" clearable placeholder="搜索已选人员" aria-label="搜索已选人员" />
        <el-table :data="filteredTargets" row-key="userId" size="small" height="380" empty-text="暂无人员，请从左侧勾选并添加" @selection-change="checkedSelected = $event">
          <el-table-column v-if="editable" type="selection" width="36" />
          <el-table-column prop="nickName" label="姓名" min-width="90" show-overflow-tooltip><template #default="{ row }">{{ row.nickName || row.userName }}{{ row.available === false ? '（失效）' : '' }}</template></el-table-column>
          <el-table-column prop="deptName" label="部门" min-width="100" show-overflow-tooltip><template #default="{ row }">{{ row.deptName || '未分配部门' }}</template></el-table-column>
          <el-table-column v-if="editable" label="操作" width="56"><template #default="{ row }"><el-button type="danger" link size="small" :aria-label="`移除${row.nickName}`" @click="emit('remove', row.userId)">移除</el-button></template></el-table-column>
        </el-table>
      </div>
    </div>
  </section>
</template>

<style scoped>
.selector-panel, .evaluator-transfer { display: grid; gap: 16px; }
.section-heading, .column-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.section-heading h2, .section-heading p { margin: 0; }
.section-heading h2 { font-size: 18px; }
.section-heading p { margin-top: 6px; color: var(--fb-text-muted, #64748b); font-size: 13px; }
.target-transfer { display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); gap: 14px; }
.target-transfer:not(:has(.transfer-actions)) { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.list-column { min-width: 0; border: 1px solid var(--fb-border, #e5e7eb); border-radius: 6px; overflow: hidden; }
.column-heading { padding: 10px 12px; background: var(--fb-surface-muted, #f8fafc); border-bottom: 1px solid var(--fb-border, #e5e7eb); font-size: 13px; }
.column-heading span, .selection-note { color: var(--fb-text-muted, #64748b); font-size: 12px; }
.participant-filter { display: flex; gap: 8px; padding: 12px; }
.participant-filter :deep(.el-form-item) { margin: 0; }
.participant-filter :deep(.el-form-item:first-child) { min-width: 0; flex: 1; }
.participant-filter :deep(.el-form-item__label) { display: none; }
.tree-scroll { height: 380px; overflow: auto; padding: 0 8px; }
.tree-scroll :deep(.el-tree-node__content) { height: 34px; }
.tree-scroll :deep(.el-tree-node__content:has(.department-node) > .el-checkbox), .tree-scroll :deep(.el-tree-node__content:has(.more-node) > .el-checkbox) { display: none; }
.department-node, .person-node { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.department-node { font-weight: 500; display: flex; align-items: center; gap: 12px; }
.person-node { display: flex; gap: 8px; flex: 1; }
.person-node small { overflow: hidden; text-overflow: ellipsis; color: var(--fb-text-muted, #64748b); }
.transfer-actions { display: flex; flex-direction: column; justify-content: center; gap: 12px; }
.transfer-actions .el-button { margin: 0; }
.selected-column > .el-input { width: calc(100% - 24px); margin: 12px; }
.selection-note { margin: 8px 12px 12px; }
.load-error { padding: 0 12px 8px; color: var(--el-color-danger); font-size: 12px; }
@media (max-width: 760px) { .target-transfer, .target-transfer:not(:has(.transfer-actions)) { grid-template-columns: 1fr; } .transfer-actions { flex-direction: row; } }
</style>
