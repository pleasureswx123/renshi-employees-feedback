<script setup>
import { SELF_RELATION_CODE } from '@/utils/publicationConfig'

const props = defineProps({
  relations: { type: Array, default: () => [] },
  editable: Boolean
})
const emit = defineEmits(['update', 'add', 'remove', 'move'])

function isSelf(row) {
  return row.relationCode === SELF_RELATION_CODE
}

function updateEnabled(row, value) {
  emit('update', row.relationCode, { isEnabled: value })
}

function updateScoring(row, value) {
  emit('update', row.relationCode, {
    isEnabled: value ? true : row.isEnabled,
    participatesInScore: value,
    weight: value && Number(row.weight) === 0 ? '100.0000' : row.weight
  })
}

function updateWeight(row, value) {
  emit('update', row.relationCode, { weight: Number(value || 0).toFixed(4) })
}
</script>

<template>
  <section class="relation-panel">
    <div class="section-heading">
      <div>
        <h2>2. 配置评价关系与权重</h2>
        <p>自己关系由系统固定维护；其他关系不自动推断人员。</p>
      </div>
      <el-button v-if="editable" @click="emit('add')">增加自定义关系</el-button>
    </div>

    <el-table :data="relations" row-key="relationCode" empty-text="暂无评价关系">
      <el-table-column label="关系名称" min-width="160">
        <template #default="{ row }">
          <el-input
            :model-value="row.relationName"
            :disabled="!editable"
            maxlength="100"
            @input="emit('update', row.relationCode, { relationName: $event })"
          />
        </template>
      </el-table-column>
      <el-table-column label="类型" width="110">
        <template #default="{ row }">
          <el-tag :type="isSelf(row) ? 'warning' : 'info'">{{ row.relationType }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="启用" width="82" align="center">
        <template #default="{ row }">
          <el-switch
            :model-value="row.isEnabled"
            :aria-label="`启用${row.relationName}`"
            :disabled="!editable || isSelf(row)"
            @change="updateEnabled(row, $event)"
          />
        </template>
      </el-table-column>
      <el-table-column label="参与计分" width="106" align="center">
        <template #default="{ row }">
          <el-checkbox
            :model-value="row.participatesInScore"
            :aria-label="`${row.relationName}参与计分`"
            :disabled="!editable || !row.isEnabled || isSelf(row)"
            @change="updateScoring(row, $event)"
          />
        </template>
      </el-table-column>
      <el-table-column label="权重（%）" width="160">
        <template #default="{ row }">
          <el-input-number
            :model-value="Number(row.weight)"
            :min="0"
            :max="100"
            :precision="4"
            :step="5"
            :disabled="!editable || !row.participatesInScore || isSelf(row)"
            controls-position="right"
            @change="updateWeight(row, $event)"
          />
        </template>
      </el-table-column>
      <el-table-column label="顺序" width="120" align="center">
        <template #default="{ row, $index }">
          <el-button
            link
            aria-label="上移关系"
            :disabled="!editable || $index === 0"
            @click="emit('move', row.relationCode, -1)"
          >
            ↑
          </el-button>
          <el-button
            link
            aria-label="下移关系"
            :disabled="!editable || $index === relations.length - 1"
            @click="emit('move', row.relationCode, 1)"
          >
            ↓
          </el-button>
        </template>
      </el-table-column>
      <el-table-column v-if="editable" label="操作" width="76" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="!row.fixed"
            type="danger"
            link
            @click="emit('remove', row.relationCode)"
          >
            删除
          </el-button>
          <span v-else class="fixed-label">固定</span>
        </template>
      </el-table-column>
    </el-table>
  </section>
</template>

<style scoped>
.relation-panel { display: grid; gap: 16px; }
.section-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.section-heading h2, .section-heading p { margin: 0; }
.section-heading h2 { font-size: 18px; }
.section-heading p { margin-top: 6px; color: #64748b; font-size: 13px; }
.fixed-label { color: #94a3b8; font-size: 12px; }
</style>
