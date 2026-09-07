<script setup>
const props = defineProps({
  summary: { type: Object, required: true },
  activeStatus: { type: String, default: '' }
})
const emit = defineEmits(['filter'])

const cards = [
  { key: 'totalCount', label: '应完成', status: '', suffix: '' },
  { key: 'submittedCount', label: '已提交', status: 'SUBMITTED', suffix: '' },
  { key: 'draftCount', label: '已暂存', status: 'DRAFT', suffix: '' },
  { key: 'pendingCount', label: '未开始', status: 'PENDING', suffix: '' },
  { key: 'closedIncompleteCount', label: '关闭未完成', status: 'CLOSED_INCOMPLETE', suffix: '' },
  { key: 'completionRate', label: '完成率', status: 'SUBMITTED', suffix: '%' }
]
</script>

<template>
  <div class="kpi-grid" aria-label="评价进度统计">
    <button
      v-for="card in cards"
      :key="card.key"
      type="button"
      class="kpi-card"
      :class="{ active: activeStatus === card.status && card.status !== '' }"
      :aria-pressed="activeStatus === card.status"
      @click="emit('filter', card.status)"
    >
      <span>{{ card.label }}</span>
      <strong>{{ props.summary[card.key] }}{{ card.suffix }}</strong>
    </button>
  </div>
</template>

<style scoped>
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 12px;
}
.kpi-card {
  display: grid;
  gap: 8px;
  min-width: 0;
  padding: 18px;
  border: 1px solid var(--fb-border, #e2e8f0);
  border-radius: 12px;
  background: var(--fb-surface, #fff);
  color: var(--fb-text-muted, #64748b);
  text-align: left;
  cursor: pointer;
  transition: border-color .2s, box-shadow .2s;
}
.kpi-card:hover,
.kpi-card:focus-visible,
.kpi-card.active {
  border-color: #409eff;
  box-shadow: 0 0 0 2px rgb(64 158 255 / 12%);
  outline: none;
}
.kpi-card strong { color: var(--fb-text-primary, #0f172a); font-size: 26px; overflow-wrap: anywhere; }
@media (max-width: 1100px) { .kpi-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 600px) {
  .kpi-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .kpi-card { padding: 14px; }
  .kpi-card strong { font-size: 22px; }
}
</style>
