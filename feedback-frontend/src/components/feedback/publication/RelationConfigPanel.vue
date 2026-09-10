<script setup>
import CircleHelpIcon from '@iconify-vue/lucide/circle-help'
import { computed, ref } from 'vue'
import { DECIMAL_FACTOR, toScaledInteger } from '@/utils/fixedDecimal'
import { SELF_RELATION_CODE } from '@/utils/publicationConfig'

const relationNames = { SUPERVISOR: '上级', PEER: '同级', SUBORDINATE: '下级', SELF: '自评', OTHER: '其他', CUSTOM: '自定义' }

const props = defineProps({
  relations: { type: Array, default: () => [] },
  editable: Boolean
})
const emit = defineEmits(['update', 'add', 'remove', 'move'])
const scoringHelp = ref()
const helpTrigger = ref()

function closeScoringHelp() {
  scoringHelp.value?.hide()
  helpTrigger.value?.$el.focus()
}

const enabledRelations = computed(() => props.relations.filter(row => row.isEnabled && !isSelf(row)))
const scoredRelations = computed(() => enabledRelations.value.filter(row => row.participatesInScore))
const referenceRelations = computed(() => enabledRelations.value.filter(row => !row.participatesInScore))
const scoringSummary = computed(() => scoredRelations.value.map(row => `${relationLabel(row)}占 ${displayWeight(row.weight)}%`).join('，'))
const referenceSummary = computed(() => referenceRelations.value.map(relationLabel).join('、'))
const weightStatus = computed(() => {
  try {
    // 只汇总配置占比，不计算正式成绩；沿用四位定点数，避免历史小数的累加误差。
    const weights = scoredRelations.value.map(row => toScaledInteger(row.weight))
    const total = weights.reduce((sum, weight) => sum + weight, 0)
    const target = 100 * DECIMAL_FACTOR
    const label = `权重合计 ${total / DECIMAL_FACTOR}%`
    if (weights.some(weight => weight < 0 || weight > target)) return { type: 'error', label, message: '每类评价的占比应在 0% 至 100% 之间' }
    if (total > target) return { type: 'error', label, message: `已超出 ${(total - target) / DECIMAL_FACTOR}%，请减少占比` }
    if (weights.some(weight => weight === 0)) return { type: 'warning', label, message: '计入总分的关系占比须大于 0%' }
    if (total < target) return { type: 'warning', label, message: `还差 ${(target - total) / DECIMAL_FACTOR}%，请补足占比` }
    return { type: 'success', label, message: '占比已达标，具体评价人在下一步安排' }
  } catch {
    return { type: 'error', label: '权重合计待确认', message: '请填写有效的占比' }
  }
})

function relationLabel(row) {
  return String(row.relationName || '').trim() || '未命名关系'
}

function displayWeight(value) {
  try { return toScaledInteger(value) / DECIMAL_FACTOR } catch { return '待填写' }
}

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
  // 用户修改时取整，保存仍沿用四位定点协议；不主动改写历史配置。
  emit('update', row.relationCode, { weight: Math.round(Number(value || 0)).toFixed(4) })
}
</script>

<template>
  <section class="relation-panel">
    <div class="section-heading">
      <div>
        <h2>4. 设置评价关系</h2>
        <p>评价指标决定“评价哪些方面、各占多少”；这里决定“哪些人的评价计入成绩、各占多少”。</p>
      </div>
      <el-button v-if="editable" @click="emit('add')">增加自定义关系</el-button>
    </div>

    <el-form :model="{ relations }">
    <el-table :data="relations" row-key="relationCode" empty-text="暂无评价关系" size="small">
      <el-table-column label="关系名称" min-width="160">
        <template #default="{ row, $index }">
          <el-form-item :prop="`relations.${$index}.relationName`" :rules="[{ required: true, whitespace: true, message: '请填写关系名称', trigger: 'blur' }]">
          <el-input
            :model-value="row.relationName"
            :disabled="!editable"
            maxlength="100"
            @input="emit('update', row.relationCode, { relationName: $event })"
          />
          </el-form-item>
        </template>
      </el-table-column>
      <el-table-column label="类型" width="110">
        <template #default="{ row }">
          <el-tag :type="isSelf(row) ? 'warning' : 'info'" size="small">{{ relationNames[row.relationType] || '自定义' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="启用评价" width="116" align="center">
        <template #header>
          <span class="column-heading">启用评价
            <el-popover trigger="click" placement="top" :width="260" content="开启后，可以在下一步安排这类人员填写问卷。">
              <template #reference><el-button class="help-button" link aria-label="了解启用评价"><el-icon><CircleHelpIcon /></el-icon></el-button></template>
            </el-popover>
          </span>
        </template>
        <template #default="{ row }">
          <span v-if="isSelf(row)" class="self-label">自动添加</span>
          <el-switch
            v-else
            :model-value="row.isEnabled"
            :aria-label="`启用${row.relationName}`"
            :disabled="!editable || isSelf(row)"
            @change="updateEnabled(row, $event)"
          />
        </template>
      </el-table-column>
      <el-table-column label="计入总分" width="116" align="center">
        <template #header>
          <span class="column-heading">计入总分
            <el-popover trigger="click" placement="top" :width="260" content="勾选后影响最终成绩；不勾选时，评价结果仅供参考。自评单独展示，仅自评的员工按自评结果计分。">
              <template #reference><el-button class="help-button" link aria-label="了解计入总分"><el-icon><CircleHelpIcon /></el-icon></el-button></template>
            </el-popover>
          </span>
        </template>
        <template #default="{ row }">
          <el-tag v-if="isSelf(row)" type="info" size="small">单独展示</el-tag>
          <el-checkbox
            v-else
            :model-value="row.participatesInScore"
            :aria-label="`${row.relationName}参与计分`"
            :disabled="!editable || !row.isEnabled || isSelf(row)"
            @change="updateScoring(row, $event)"
          />
        </template>
      </el-table-column>
      <el-table-column label="占比（%）" width="160">
        <template #header>
          <span class="column-heading">占比（%）
            <el-popover trigger="click" placement="top" :width="280" content="占比也叫权重，表示这类评价对成绩的影响程度。计入总分的关系占比合计须为 100%；同类多人共享这一占比，先取平均分。">
              <template #reference><el-button class="help-button" link aria-label="了解占比"><el-icon><CircleHelpIcon /></el-icon></el-button></template>
            </el-popover>
          </span>
        </template>
        <template #default="{ row }">
          <span v-if="isSelf(row)" class="self-label">仅自评时计分</span>
          <!-- 当前Element Plus版本仅在挂载时设置aria-disabled，禁用状态改变时重建并保留绑定值。 -->
          <el-input-number
            v-else
            :key="String(!editable || !row.participatesInScore || isSelf(row))"
            :model-value="Number(row.weight)"
            :aria-label="`${row.relationName}权重（%）`"
            :min="0"
            :max="100"
            :step="1"
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
    </el-form>

    <section class="scoring-summary" aria-label="当前计分方式">
      <div class="summary-config" aria-live="polite">
        <p class="summary-main"><strong>当前计分方式：</strong>{{ scoringSummary ? `${scoringSummary}。` : '尚未设置计分关系，请启用需要的关系并勾选“计入总分”。' }}</p>
        <p v-if="referenceSummary" class="reference-note">仅供参考：{{ referenceSummary }}，不计入总分。</p>
      </div>
      <el-alert class="summary-status" :type="weightStatus.type" :closable="false" show-icon aria-live="polite">
        <template #title><span class="weight-summary"><strong>{{ weightStatus.label }}</strong><span>{{ weightStatus.type === 'success' ? '占比已达标' : weightStatus.message }}</span></span></template>
      </el-alert>
      <el-popover
        ref="scoringHelp"
        trigger="click"
        placement="top-end"
        :width="640"
        :popper-style="{ maxWidth: 'calc(100vw - 32px)', boxSizing: 'border-box' }"
      >
        <template #reference><el-button ref="helpTrigger" class="scoring-help-trigger" type="primary" link size="small" @keydown.esc.stop="closeScoringHelp"><el-icon><CircleHelpIcon /></el-icon>分数怎么算？</el-button></template>
        <section class="scoring-guide" aria-label="计分规则说明" tabindex="0" @keydown.esc.stop="closeScoringHelp">
          <div class="guide-heading"><strong>计分规则说明</strong><el-button link size="small" @click="closeScoringHelp">关闭说明</el-button></div>
          <p class="summary-note">同类多人评价先取平均。自评单独展示；未分配他评的员工按自评结果计分。</p>
          <div class="example-heading"><strong>从题目到最终成绩</strong><el-tag size="small" type="info">演示数据</el-tag></div>
          <p class="summary-note">下面固定用“上级 60%、同级 40%；工作能力 70%、协作 30%”举例，与当前配置无关。</p>
          <ol class="scoring-example">
            <li><strong>题目换成百分制</strong><p>某份答卷中，“工作能力”绑定题目满分合计 10 分，得到 9 分。</p><div class="example-formula">9 ÷ 10 × 100 = <strong>90 分</strong></div></li>
            <li><strong>合并不同人的评价</strong><p>上级给工作能力 90 分，同级平均给 80 分。两名同级分别给 70、90 分时，平均就是 80 分。</p><div class="example-formula">90 × 60% + 80 × 40% = <strong>86 分</strong></div></li>
            <li><strong>按指标占比算总分</strong><p>工作能力占 70%，协作占 30%；假设协作按同样方法算出 84 分。</p><div class="example-formula">86 × 70% + 84 × 30% = <strong>85.4 分</strong></div></li>
          </ol>
          <el-collapse class="missing-help">
            <el-collapse-item title="有人未提交或漏答，会怎样？" name="missing">
              <p>只统计已提交的答卷。同类有人未提交时，只对已提交的评价取平均。</p>
              <p>某类计分评价全部未提交时，不把它当作 0 分，其占比按比例分配给有有效答卷的计分关系。例如上级 60%、同级 40%，只有上级提交时，上级实际占比为 100%；报告会标明缺失情况。</p>
              <p>需要他评却没有有效他评数据时，成绩显示“数据不足”，不会用自评补上。发布时已确定仅自评的员工，按自评结果计分。</p>
              <p>已提交答卷漏答非必答计分题时，该题不增加得分，指标满分不减少；报告会记录漏答情况。</p>
            </el-collapse-item>
          </el-collapse>
        </section>
      </el-popover>
    </section>
  </section>
</template>

<style scoped>
/* 约束网格列的最小宽度，避免保存期间表格操作列增删将整张卡片撑宽。 */
.relation-panel { display: grid; grid-template-columns: minmax(0, 1fr); gap: 12px; }
.section-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.section-heading h2, .section-heading p { margin: 0; }
.section-heading h2 { font-size: 18px; }
.section-heading p { margin-top: 6px; color: var(--fb-text-muted, #64748b); font-size: 13px; }
.fixed-label { color: var(--fb-text-muted, #94a3b8); font-size: 12px; }
.relation-panel:deep(.el-form-item) { margin: 0 0 12px; }
.relation-panel:deep(.el-input-number) { width: 140px; }
.column-heading { display: inline-flex; align-items: center; gap: 4px; white-space: nowrap; }
.help-button { padding: 4px; color: var(--el-text-color-secondary); }
.help-button:focus-visible { outline: 2px solid var(--el-color-primary); outline-offset: 2px; }
.self-label { color: var(--el-text-color-secondary); font-size: 12px; }
.scoring-summary { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 12px; min-width: 0; padding: 8px 12px; border: 1px solid var(--el-color-primary-light-8); border-radius: 6px; background: var(--el-color-primary-light-9); }
.summary-config { flex: 1 1 280px; min-width: 0; }
.summary-main { margin: 0; font-size: 13px; line-height: 1.6; overflow-wrap: anywhere; }
.reference-note { margin: 2px 0 0; color: var(--el-text-color-regular); font-size: 12px; overflow-wrap: anywhere; }
.summary-status { flex: 0 1 auto; width: auto; max-width: 100%; padding: 4px 8px; }
.summary-status:deep(.el-alert__title) { font-size: 12px; line-height: 20px; }
.scoring-help-trigger { flex-shrink: 0; height: 24px; gap: 4px; }
.scoring-guide { max-height: min(540px, calc(100dvh - 100px)); overflow-y: auto; padding-right: 4px; color: var(--el-text-color-primary); line-height: 1.6; }
.scoring-guide:focus-visible { outline: 2px solid var(--el-color-primary); outline-offset: 2px; }
.guide-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 8px; }
.summary-note { margin: 4px 0 10px; color: var(--el-text-color-regular); font-size: 12px; line-height: 1.6; }
.weight-summary { display: flex; flex-wrap: wrap; align-items: center; gap: 2px 8px; }
.example-heading { display: flex; align-items: center; gap: 8px; margin: 8px 0 4px; }
.scoring-example { display: grid; gap: 8px; margin: 10px 0; padding: 0; list-style-position: inside; }
.scoring-example li { padding: 8px 10px; border: 1px solid var(--el-border-color-light); border-radius: 4px; background: var(--el-fill-color-light); }
.scoring-example li::marker { color: var(--el-color-primary); font-weight: 600; }
.scoring-example p { margin: 6px 0; color: var(--el-text-color-regular); }
.example-formula { color: var(--el-color-primary); font-variant-numeric: tabular-nums; }
.missing-help { border-bottom: 0; }
.missing-help:deep(.el-collapse-item__header) { min-height: 36px; height: auto; line-height: 1.5; }
.missing-help:deep(.el-collapse-item__wrap) { border-bottom: 0; }
.missing-help:deep(.el-collapse-item__content) { padding-bottom: 0; }
.missing-help p { margin: 6px 0; color: var(--el-text-color-regular); }
</style>
