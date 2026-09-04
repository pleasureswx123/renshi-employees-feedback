<script setup>
import { computed, reactive, ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  precheck: { type: Object, default: null },
  completing: { type: Boolean, default: false }
})
const emit = defineEmits(['update:modelValue', 'submit'])

const formRef = ref()
const form = reactive({ completionReason: '', confirmed: false })
const remainingCount = computed(() => (props.precheck?.summary?.pendingCount || 0) + (props.precheck?.summary?.draftCount || 0))
const earlyCompletion = computed(() => props.precheck?.projectStatus === 'ACTIVE' && remainingCount.value > 0)

function validateReason(_rule, value, callback) {
  const normalized = String(value || '').trim()
  if (!normalized) return callback(new Error('请填写完成原因'))
  if (Array.from(normalized).length > 500) return callback(new Error('完成原因不能超过500个字符'))
  callback()
}

const rules = {
  completionReason: [{ validator: validateReason, trigger: ['blur', 'change'] }]
}

watch(
  () => props.modelValue,
  visible => {
    if (visible) {
      form.completionReason = ''
      form.confirmed = false
      formRef.value?.clearValidate()
    }
  }
)

function close() {
  if (!props.completing) emit('update:modelValue', false)
}

async function submit() {
  if (props.completing || !form.confirmed || !props.precheck?.canComplete) return
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  emit('submit', form.completionReason.trim())
}
</script>

<template>
  <el-drawer
    :model-value="modelValue"
    :title="earlyCompletion ? '提前结束项目确认' : '完成项目实时预检'"
    direction="rtl"
    size="75%"
    class="completion-drawer"
    :close-on-click-modal="!completing"
    :close-on-press-escape="!completing"
    :show-close="!completing"
    @close="close"
  >
    <template v-if="precheck">
      <el-alert
        v-if="!precheck.dataScopeComplete"
        title="当前数据范围仅覆盖部分被评价人"
        description="局部统计不能代表整个项目，也不能执行项目完成。"
        type="warning"
        :closable="false"
        show-icon
      />
      <el-alert
        v-else-if="precheck.projectStatus === 'COMPLETED'"
        title="项目已经完成"
        description="以下为已完成结果，只读展示，不支持重新打开。"
        type="success"
        :closable="false"
        show-icon
      />
      <el-alert
        v-else-if="earlyCompletion"
        :title="`还有 ${remainingCount} 份评价未提交`"
        :description="`确认后，剩余 ${remainingCount} 份任务将关闭，员工不能继续填写；报告仅使用 ${precheck.summary.submittedCount} 份已提交答卷。项目结束后不能重新打开。`"
        type="warning"
        :closable="false"
        show-icon
        class="early-completion-warning"
      />
      <dl v-if="precheck.projectStatus === 'COMPLETED'" class="completion-audit">
        <div>
          <dt>完成操作人ID：</dt>
          <dd>{{ precheck.completedBy ?? '—' }}</dd>
        </div>
        <div>
          <dt>完成时间：</dt>
          <dd>{{ precheck.completedTime?.replace('T', ' ') || '—' }}</dd>
        </div>
        <div>
          <dt>完成原因：</dt>
          <dd>{{ precheck.completionReason || '—' }}</dd>
        </div>
      </dl>

      <section class="precheck-section" aria-label="最新回收快照">
        <h3>最新回收快照</h3>
        <p class="snapshot-time">预检时间：{{ precheck.precheckedAt?.replace('T', ' ') || '—' }}</p>
        <div class="summary-grid">
          <span>应完成 <strong>{{ precheck.summary.totalCount }}</strong></span>
          <span>已提交 <strong>{{ precheck.summary.submittedCount }}</strong></span>
          <span>已暂存 <strong>{{ precheck.summary.draftCount }}</strong></span>
          <span>未开始 <strong>{{ precheck.summary.pendingCount }}</strong></span>
          <span>关闭未完成 <strong>{{ precheck.summary.closedIncompleteCount }}</strong></span>
          <span>完成率 <strong>{{ precheck.summary.completionRate }}%</strong></span>
        </div>
      </section>

      <section class="precheck-section">
        <h3>缺失关系</h3>
        <div v-if="precheck.missingRelations?.length" class="missing-list">
          <article v-for="item in precheck.missingRelations" :key="`${item.targetUserId}-${item.relationId}`">
            <strong>{{ item.targetName }} · {{ item.relationName }}</strong>
            <span>已提交 {{ item.submittedCount }}/{{ item.assignmentCount }}</span>
          </article>
        </div>
        <el-empty v-else description="没有完全缺失的评价关系" :image-size="72" />
      </section>

      <section class="precheck-section">
        <h3>完成影响</h3>
        <ul class="impact-list">
          <li v-for="message in precheck.impactMessages || []" :key="message">{{ message }}</li>
        </ul>
      </section>

      <el-form
        v-if="precheck.projectStatus === 'ACTIVE' && precheck.dataScopeComplete && precheck.canComplete"
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        class="completion-form"
      >
        <el-form-item label="完成原因" prop="completionReason">
          <el-input
            v-model="form.completionReason"
            type="textarea"
            :rows="4"
            :placeholder="earlyCompletion ? '说明评价尚未全部提交时，提前结束本轮项目的原因' : '填写本次结束项目的真实业务原因'"
            :disabled="completing"
          />
        </el-form-item>
        <p class="unicode-count">{{ Array.from(form.completionReason.trim()).length }}/500 个字符</p>
        <el-form-item>
          <el-checkbox v-model="form.confirmed" :disabled="completing">
            <template v-if="earlyCompletion">我已知晓提前结束不可撤销，剩余 {{ remainingCount }} 份未提交任务将关闭且不能继续作答</template>
            <template v-else>我已阅读最新预检，确认完成不可撤销，项目不能重新打开</template>
          </el-checkbox>
        </el-form-item>
      </el-form>
    </template>

    <template #footer>
      <el-button :disabled="completing" @click="close">关闭</el-button>
      <el-button
        v-if="precheck?.projectStatus === 'ACTIVE' && precheck?.dataScopeComplete && precheck?.canComplete"
        type="danger"
        :loading="completing"
        :disabled="completing || !form.confirmed"
        @click="submit"
      >
        {{ earlyCompletion ? '确认提前结束' : '确认完成项目' }}
      </el-button>
    </template>
  </el-drawer>
</template>

<style scoped>
.precheck-section { min-width: 0; max-width: 100%; margin-bottom: 24px; }
.early-completion-warning { margin-bottom: 20px; }
.precheck-section h3 { margin: 0 0 12px; color: var(--fb-text-primary, #0f172a); }
.snapshot-time,
.unicode-count { margin: 0 0 12px; color: var(--fb-text-muted, #64748b); font-size: 13px; }
.summary-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.summary-grid span,
.missing-list article { padding: 12px; border: 1px solid var(--fb-border, #e2e8f0); border-radius: 8px; background: var(--fb-surface-muted, #f8fafc); }
.summary-grid strong { display: block; margin-top: 5px; color: var(--fb-text-primary, #0f172a); font-size: 20px; }
.missing-list { display: grid; gap: 8px; }
.missing-list article { display: flex; justify-content: space-between; gap: 12px; }
.missing-list span { color: var(--fb-text-muted, #64748b); }
.impact-list { max-width: 100%; margin: 0; padding-left: 20px; color: var(--fb-text-regular, #475569); line-height: 1.8; overflow-wrap: anywhere; }
.completion-audit { display: grid; gap: 10px; margin: 16px 0 24px; }
.completion-audit div { display: grid; grid-template-columns: 120px minmax(0, 1fr); gap: 12px; }
.completion-audit dt { color: var(--fb-text-muted, #64748b); }
.completion-audit dd { min-width: 0; margin: 0; color: var(--fb-text-primary, #0f172a); overflow-wrap: anywhere; }
.completion-form { min-width: 0; max-width: 100%; padding-top: 20px; border-top: 1px solid var(--fb-border, #e2e8f0); }
.completion-form:deep(.el-form-item__content) { min-width: 0; max-width: 100%; }
.completion-form:deep(.el-checkbox) {
  align-items: flex-start;
  width: 100%;
  max-width: 100%;
  height: auto;
  white-space: normal;
}
.completion-form:deep(.el-checkbox__input) { margin-top: 3px; }
.completion-form:deep(.el-checkbox__label) {
  min-width: 0;
  max-width: calc(100% - 22px);
  line-height: 1.55;
  white-space: normal;
  overflow-wrap: anywhere;
}
:global(.completion-drawer) { position: fixed; right: 0; width: min(760px, 75vw) !important; }
:global(.completion-drawer .el-drawer__body) { min-width: 0; max-width: 100%; overflow-x: hidden; }
@media (max-width: 600px) {
  :global(.completion-drawer) { width: 100vw !important; }
  .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .missing-list article { align-items: flex-start; flex-direction: column; }
  .completion-audit div { grid-template-columns: minmax(0, 1fr); gap: 4px; }
}
</style>
