<script setup>
import { computed, ref, watchEffect } from 'vue'

import { SELF_RELATION_CODE } from '@/utils/publicationConfig'

const props = defineProps({
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

const selectableRelations = computed(() =>
  props.relations.filter(item => item.isEnabled && item.relationCode !== SELF_RELATION_CODE)
)
const selectedIds = computed(() =>
  props.selections.find(
    item => item.targetUserId === targetUserId.value && item.relationCode === relationCode.value
  )?.evaluatorUserIds || []
)
const participantById = computed(() => new Map(props.participants.map(item => [item.userId, item])))
const selectedParticipants = computed(() =>
  selectedIds.value.map(userId => participantById.value.get(userId) || {
    userId,
    nickName: `用户${userId}`,
    deptName: null,
    available: false
  })
)

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

function search() {
  emit('search', keyword.value.trim())
}
</script>

<template>
  <section class="evaluator-panel">
    <div class="section-heading">
      <div>
        <h2>3. 分配评价人</h2>
        <p>按被评价人与关系明确选择；每个目标的自评由后端自动添加。</p>
      </div>
    </div>

    <el-alert
      title="系统会为每名被评价人自动生成一项“自己”评价，客户端不能删除或伪造。"
      type="info"
      :closable="false"
      show-icon
    />

    <el-form inline :model="{ targetUserId, relationCode }" class="context-form">
      <el-form-item label="被评价人">
        <el-select v-model="targetUserId" placeholder="选择被评价人" style="width: 220px">
          <el-option
            v-for="item in targets"
            :key="item.userId"
            :label="item.nickName"
            :value="item.userId"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="评价关系">
        <el-select v-model="relationCode" placeholder="先启用非自评关系" style="width: 220px">
          <el-option
            v-for="item in selectableRelations"
            :key="item.relationCode"
            :label="item.relationName"
            :value="item.relationCode"
          />
        </el-select>
      </el-form-item>
    </el-form>

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
            @keyup.enter="search"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="search">查询</el-button>
        </el-form-item>
      </el-form>

      <div class="dual-list">
        <div class="list-column">
          <strong>可选评价人</strong>
          <el-table v-loading="loading" :data="candidateRows" size="small">
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
          <strong>已选评价人（{{ selectedParticipants.length }}）</strong>
          <el-table :data="selectedParticipants" size="small" empty-text="当前关系尚未选择评价人">
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
.evaluator-panel { display: grid; gap: 16px; }
.section-heading h2, .section-heading p { margin: 0; }
.section-heading h2 { font-size: 18px; }
.section-heading p { margin-top: 6px; color: #64748b; font-size: 13px; }
.context-form, .participant-filter { margin-bottom: -8px; }
.dual-list { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 18px; }
.list-column { min-width: 0; padding: 14px; border: 1px solid #e5e7eb; border-radius: 8px; }
.list-column > strong { display: block; margin-bottom: 10px; }
.selected-column { background: #f8fafc; }
.mini-pagination { justify-content: flex-end; margin-top: 14px; }
@media (max-width: 980px) { .dual-list { grid-template-columns: 1fr; } }
</style>
