<script setup>
import { ref } from 'vue'

const props = defineProps({
  rows: { type: Array, default: () => [] },
  total: { type: Number, default: 0 },
  pageNum: { type: Number, default: 1 },
  pageSize: { type: Number, default: 10 },
  selectedTargets: { type: Array, default: () => [] },
  loading: Boolean,
  editable: Boolean
})
const emit = defineEmits(['search', 'page-change', 'add', 'remove'])
const keyword = ref('')

function isSelected(userId) {
  return props.selectedTargets.some(item => item.userId === userId)
}

function search() {
  emit('search', keyword.value.trim())
}
</script>

<template>
  <section class="selector-panel">
    <div class="section-heading">
      <div>
        <h2>1. 选择被评价人</h2>
        <p>候选人员由后端按当前账号的数据范围分页返回。</p>
      </div>
      <el-tag type="info">已选 {{ selectedTargets.length }} 人</el-tag>
    </div>

    <el-form inline :model="{ keyword }" class="participant-filter">
      <el-form-item label="人员搜索">
        <el-input
          v-model="keyword"
          clearable
          placeholder="输入账号或姓名"
          @keyup.enter="search"
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="loading" @click="search">查询</el-button>
      </el-form-item>
    </el-form>

    <div class="dual-list">
      <div class="list-column">
        <strong>可选人员</strong>
        <el-table v-loading="loading" :data="rows" size="small" empty-text="没有符合条件的人员">
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
                :disabled="isSelected(row.userId)"
                @click="emit('add', row)"
              >
                {{ isSelected(row.userId) ? '已选' : '添加' }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-pagination
          class="mini-pagination"
          size="small"
          background
          layout="total, prev, pager, next"
          :total="total"
          :page-size="pageSize"
          :current-page="pageNum"
          @current-change="emit('page-change', $event)"
        />
      </div>

      <div class="list-column selected-column">
        <strong>已选被评价人</strong>
        <el-table :data="selectedTargets" size="small" empty-text="尚未选择被评价人">
          <el-table-column prop="nickName" label="姓名" min-width="120" />
          <el-table-column prop="deptName" label="部门" min-width="130">
            <template #default="{ row }">{{ row.deptName || '未分配部门' }}</template>
          </el-table-column>
          <el-table-column label="任务模式" width="94">
            <template #default="{ row }">
              <el-tag :type="row.onlySelfEvaluation ? 'warning' : 'success'" size="small">
                {{ row.onlySelfEvaluation ? '仅自评' : '含他评' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column v-if="editable" label="操作" width="76" fixed="right">
            <template #default="{ row }">
              <el-button type="danger" link @click="emit('remove', row.userId)">移除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>
  </section>
</template>

<style scoped>
.selector-panel { display: grid; gap: 16px; }
.section-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.section-heading h2, .section-heading p { margin: 0; }
.section-heading h2 { font-size: 18px; }
.section-heading p { margin-top: 6px; color: #64748b; font-size: 13px; }
.participant-filter { margin-bottom: -8px; }
.dual-list { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 18px; }
.list-column { min-width: 0; padding: 14px; border: 1px solid #e5e7eb; border-radius: 8px; }
.list-column > strong { display: block; margin-bottom: 10px; }
.selected-column { background: #f8fafc; }
.mini-pagination { justify-content: flex-end; margin-top: 14px; }
@media (max-width: 980px) { .dual-list { grid-template-columns: 1fr; } }
</style>
