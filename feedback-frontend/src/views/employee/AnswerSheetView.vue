<script setup>
import ArrowLeftIcon from '@iconify-vue/lucide/arrow-left'
import ArrowRightIcon from '@iconify-vue/lucide/arrow-right'
import CircleCheckIcon from '@iconify-vue/lucide/circle-check'
import InfoIcon from '@iconify-vue/lucide/info'
import ListChecksIcon from '@iconify-vue/lucide/list-checks'
import PencilLineIcon from '@iconify-vue/lucide/pencil-line'
import RefreshCwIcon from '@iconify-vue/lucide/refresh-cw'
import SaveIcon from '@iconify-vue/lucide/save'
import SendIcon from '@iconify-vue/lucide/send'
import UserRoundIcon from '@iconify-vue/lucide/user-round'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import RichTextEditor from '@/components/feedback/RichTextEditor.vue'
import QuestionRenderer from '@/components/feedback/questions/QuestionRenderer.vue'
import { useAnswerSheetStore } from '@/stores/answerSheet'
import { useAuthStore } from '@/stores/auth'
import { usePermissionStore } from '@/stores/permission'
import { answerErrors, TASK_STATUS_LABELS } from '@/utils/answerSheet'
import { formatDateTime } from '@/utils/displayFormat'

const props = defineProps({ history: { type: Boolean, default: false } })
const route = useRoute()
const router = useRouter()
const store = useAnswerSheetStore()
const auth = useAuthStore()
const permission = usePermissionStore()
const form = ref()
const confirming = ref(false)
const requiredValidation = ref(false)
const canEdit = computed(() => store.editable && permission.hasAnyPermission(['feedback:task:answer', 'feedback:task:submit']))
const disabled = computed(() => store.busy || confirming.value || !canEdit.value || store.conflict)
const pages = computed(() => store.detail?.questionnaire.pages || [])
const rulesFor = question => [{ validator: (_rule, value, callback) => {
  const message = answerErrors(question, value, { required: requiredValidation.value })[0]
  callback(message ? new Error(message) : undefined)
}, trigger: 'change' }]

watch(() => [route.params.assignmentId, props.history], ([id, history]) => {
  confirming.value = false
  requiredValidation.value = false
  store.load(id, { history })
}, { immediate: true })

async function updateAnswer(question, answer) {
  if (disabled.value) return
  const epoch = store.contextEpoch
  store.setAnswer(question.questionCode, answer)
  if (store.issues.length) store.validate(requiredValidation.value)
  // 子组件更新事件先于ElFormItem读取新值，等待Store水合后再校验当前字段。
  await nextTick()
  if (epoch === store.contextEpoch) await form.value?.validateField([['answers', question.questionCode]]).catch(() => false)
}

async function focusIssue(issue) {
  const index = pages.value.findIndex(page => page.pageId === issue?.pageId)
  if (index >= 0) store.setPage(index)
  await nextTick()
  const question = store.questions.find(item => item.question.questionId === issue?.questionId)?.question
  if (question) form.value?.scrollToField(['answers', question.questionCode])
}

function issueLabel(issue) {
  const item = store.questions.find(({ question }) => question.questionId === issue.questionId)
  return item ? `${item.page.pageTitle} · ${item.question.title}：${issue.message}` : issue.message
}

async function validate(required) {
  requiredValidation.value = required
  await nextTick()
  const valid = store.validate(required)
  const formValid = await form.value.validate().catch(() => false)
  if (!valid || !formValid) {
    await focusIssue(store.issues[0])
    return false
  }
  return true
}

async function save() {
  if (disabled.value || !permission.hasPermission('feedback:task:answer')) return
  confirming.value = true
  const epoch = store.contextEpoch
  try {
    if (!await validate(false) || epoch !== store.contextEpoch) return
    const result = await store.save()
    if (result) {
      form.value?.clearValidate()
      ElMessage.success('答卷已暂存，可稍后继续填写')
    }
    else if (epoch === store.contextEpoch && store.issues.length) await focusIssue(store.issues[0])
  } finally {
    if (epoch === store.contextEpoch) confirming.value = false
  }
}

async function submit() {
  if (disabled.value || !permission.hasPermission('feedback:task:submit')) return
  confirming.value = true
  const epoch = store.contextEpoch
  try {
    if (!await validate(true) || epoch !== store.contextEpoch) return
    await ElMessageBox.confirm(
      `即将提交对“${store.detail.task.targetName}”的${store.detail.task.relationName}评价。提交后不能修改，其他评价任务不受影响。`,
      '确认提交本份评价',
      { type: 'warning', confirmButtonText: '确认提交', cancelButtonText: '继续检查', closeOnClickModal: false }
    )
    if (epoch !== store.contextEpoch) return
    const result = await store.submit()
    if (result) ElMessage.success('评价已提交')
    else if (store.issues.length) await focusIssue(store.issues[0])
  } catch (failure) {
    if (!['cancel', 'close'].includes(failure)) ElMessage.error(failure.message || '提交失败')
  } finally {
    if (epoch === store.contextEpoch) confirming.value = false
  }
}

async function mayLeave() {
  if (!auth.token) return true
  if (store.busy) { ElMessage.warning('正在处理请求，请稍候'); return false }
  if (!store.dirty) return true
  try {
    await ElMessageBox.confirm('当前修改尚未暂存，离开后将丢失这些修改。', '离开答题页面？', {
      confirmButtonText: '放弃修改并离开', cancelButtonText: '继续填写', type: 'warning'
    })
    return true
  } catch { return false }
}

async function reload() {
  if (!await mayLeave()) return
  await store.load(route.params.assignmentId, { history: props.history })
}

function beforeUnload(event) {
  if (!store.dirty && !store.busy) return
  event.preventDefault()
  event.returnValue = ''
}

function handleEnter(event) {
  if (event.target.tagName === 'TEXTAREA' || event.target.tagName === 'BUTTON') return
  event.preventDefault()
  if (event.ctrlKey || event.metaKey) submit()
}

function back() {
  router.push(props.history ? '/employee/reviews' : store.detail ? `/employee/todos/${store.detail.task.projectId}` : '/employee/todos')
}

onBeforeRouteLeave(mayLeave)
onBeforeRouteUpdate(mayLeave)
onMounted(() => window.addEventListener('beforeunload', beforeUnload))
onBeforeUnmount(() => { window.removeEventListener('beforeunload', beforeUnload); store.reset() })
</script>

<template>
  <section v-loading="store.loading" class="answer-workspace">
    <div class="answer-top-actions">
      <el-button :icon="ArrowLeftIcon" @click="back">{{ history ? '返回我评价的' : '返回任务列表' }}</el-button>
      <el-button :icon="RefreshCwIcon" :disabled="store.busy || confirming" @click="reload">重新加载</el-button>
    </div>
    <el-alert v-if="store.error" :title="store.error" type="error" :closable="false" class="answer-notice" />
    <el-button
      v-if="!store.detail && store.closed && permission.hasPermission('feedback:history:view')"
      @click="router.push(`/employee/reviews/${route.params.assignmentId}`)"
    >查看已提交答案</el-button>
    <template v-if="store.detail">
      <header class="answer-header workspace-page-header">
        <div>
        <p>{{ store.detail.task.projectName }}</p>
        <h1 class="page-heading answer-heading"><UserRoundIcon width="22" height="22" class="heading-icon" aria-hidden="true" /><span>{{ history ? '已提交的评价' : '评价' }}：{{ store.detail.task.targetName }}</span></h1>
        <p>{{ store.detail.task.targetDeptName || '未配置部门' }} · {{ store.detail.task.relationName }}评价</p>
        </div>
        <el-tag :type="store.detail.task.status === 'SUBMITTED' ? 'success' : 'warning'">{{ TASK_STATUS_LABELS[store.detail.task.status] }}</el-tag>
      </header>
      <el-alert
        v-if="store.detail.task.status === 'SUBMITTED'"
        title="这份评价已提交，答案不可修改。" type="success" :closable="false" class="answer-notice"
      />
      <el-alert v-else-if="!store.editable" title="项目或任务已关闭，不能继续答题。" type="info" :closable="false" class="answer-notice" />
      <el-alert v-else-if="!canEdit" title="当前账号仅有查看权限，不能填写或提交答案。" type="info" :closable="false" class="answer-notice" />
      <section class="answer-progress" aria-label="答题进度">
          <span class="progress-label"><ListChecksIcon width="16" height="16" aria-hidden="true" />已作答 {{ store.answeredCount }}/{{ store.questions.length }} 题</span>
          <el-progress :percentage="store.questions.length ? Math.round(store.answeredCount / store.questions.length * 100) : 0" />
      </section>
      <el-card shadow="never" class="answer-document">
        <h2>{{ store.detail.questionnaire.title }}</h2>
        <RichTextEditor v-if="store.detail.questionnaire.descriptionDoc" :model-value="store.detail.questionnaire.descriptionDoc" readonly />
        <p v-else-if="store.detail.questionnaire.description" class="description">{{ store.detail.questionnaire.description }}</p>
        <el-alert v-if="store.issues.length" title="请检查以下题目" type="warning" :closable="false" class="answer-notice">
          <div v-for="(issue, index) in store.issues" :key="index">
            <el-button link type="primary" class="issue-link" @click="focusIssue(issue)">{{ issueLabel(issue) }}</el-button>
          </div>
        </el-alert>
        <el-form ref="form" :model="store" :disabled="disabled" label-position="top" @keydown.enter="handleEnter">
          <section v-for="(page, pageIndex) in pages" v-show="store.pageIndex === pageIndex" :key="page.pageId" class="answer-page">
            <el-form-item
              v-for="(question, questionIndex) in page.questions"
              :key="question.questionCode"
              :prop="['answers', question.questionCode]"
              :rules="rulesFor(question)"
              :data-question-id="question.questionId"
              class="answer-question"
            >
              <div class="answer-question-heading">
                <span v-if="question.isRequired" class="required-mark" aria-label="必答">*</span>
                <strong>第 {{ pages.slice(0, pageIndex).reduce((count, item) => count + item.questions.length, 0) + questionIndex + 1 }} 题：{{ question.title }}</strong>
              </div>
              <p v-if="question.description" class="question-description">{{ question.description }}</p>
              <QuestionRenderer
                :question="question"
                :show-heading="false"
                :mode="canEdit ? 'answer' : 'readonly'"
                :model-value="store.answers[question.questionCode]"
                @update:model-value="updateAnswer(question, $event)"
              />
            </el-form-item>
          </section>
        </el-form>
        <div class="page-navigation">
          <el-button :icon="ArrowLeftIcon" :disabled="store.pageIndex === 0 || store.busy || confirming" @click="store.setPage(store.pageIndex - 1)">上一页</el-button>
          <span>{{ store.pageIndex + 1 }}/{{ pages.length }}</span>
          <el-button :disabled="store.pageIndex === pages.length - 1 || store.busy || confirming" @click="store.setPage(store.pageIndex + 1)">下一页<ArrowRightIcon width="14" height="14" class="next-page-icon" aria-hidden="true" /></el-button>
        </div>
      </el-card>
      <footer class="answer-footer">
        <div class="save-state" :class="{ 'is-unsaved': store.dirty, 'is-saved': !store.dirty && !!store.detail.task.savedTime }" role="status">
          <PencilLineIcon v-if="store.dirty" width="16" height="16" class="state-icon" aria-hidden="true" />
          <CircleCheckIcon v-else-if="store.detail.task.savedTime" width="16" height="16" class="state-icon" aria-hidden="true" />
          <InfoIcon v-else width="16" height="16" class="state-icon" aria-hidden="true" />
          <span v-if="store.dirty">修改未暂存</span>
          <span v-else-if="store.detail.task.savedTime">最近保存：{{ formatDateTime(store.detail.task.savedTime) }}</span>
          <span v-else>填写部分答案后也可以暂存</span>
        </div>
        <div v-if="canEdit" class="write-actions">
          <el-button v-if="permission.hasPermission('feedback:task:answer')" :icon="SaveIcon" :loading="store.saving" :disabled="disabled" @click="save">暂存答卷</el-button>
          <el-button v-if="permission.hasPermission('feedback:task:submit')" :icon="SendIcon" type="primary" :loading="store.submitting" :disabled="disabled" @click="submit">提交本份评价</el-button>
        </div>
        <el-button v-else-if="!history && permission.hasPermission('feedback:task:view')" :icon="ArrowRightIcon" type="primary" @click="back">继续处理其他任务</el-button>
      </footer>
    </template>
  </section>
</template>

<style scoped>
.answer-workspace { max-width: 900px; min-height: 240px; margin: auto; }
.answer-header { margin: 18px 0; overflow-wrap: anywhere; }
.answer-header p { margin: 0; font-size: 13px; }
.answer-top-actions { display: flex; gap: 12px; flex-wrap: wrap; }
.answer-top-actions .el-button { margin-left: 0; }
.answer-header h1 { font-size: 24px; margin: 8px 0; }
.answer-heading { display: flex; align-items: center; gap: 8px; }
.heading-icon { flex-shrink: 0; color: var(--el-color-primary); }
.answer-header p, .description { color: var(--fb-text-muted, #64748b); white-space: pre-wrap; line-height: 1.7; }
.answer-notice { margin: 16px 0; }
.answer-document h2 { overflow-wrap: anywhere; }
.answer-document h2 { font-size: 20px; font-weight: 600; text-align: center; }
.answer-progress { display: grid; gap: 8px; margin: 0 0 18px; padding: 14px 20px; border: 1px solid var(--fb-primary-border, #d9e8f8); border-radius: 6px; background: var(--fb-primary-bg, #f0f7ff); color: var(--fb-text-regular, #475569); font-size: 13px; }
.progress-label { display: flex; align-items: center; gap: 6px; }
.answer-page { margin-top: 8px; }
.answer-question { padding: 20px 0; border-bottom: 1px solid var(--fb-border, #e5e7eb); }
.answer-question-heading { margin-bottom: 12px; color: var(--fb-text-primary, #111827); line-height: 1.7; }
.required-mark { margin-right: 4px; color: #f56c6c; }
.question-description { margin: 0 0 12px; color: var(--fb-text-muted, #64748b); white-space: pre-wrap; line-height: 1.7; }
.answer-question:deep(.el-form-item__content) { display: block; min-width: 0; overflow-wrap: anywhere; }
.answer-question:deep(.el-form-item__error) { position: static; padding-top: 8px; }
.issue-link { height: auto; white-space: normal; text-align: left; line-height: 1.7; }
.page-navigation { display: flex; justify-content: space-between; align-items: center; margin-top: 24px; }
.next-page-icon { margin-left: 6px; }
.answer-footer { position: sticky; bottom: calc(16px + env(safe-area-inset-bottom)); display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 12px 18px; margin: 20px 12px 0; background: var(--fb-surface, #fff); border: 1px solid var(--fb-border, #e2e8f0); border-radius: 12px; box-shadow: 0 4px 20px rgb(15 23 42 / 8%), 0 1px 3px rgb(15 23 42 / 4%); z-index: 5; }
.save-state { display: flex; align-items: center; gap: 8px; min-width: 0; color: var(--fb-text-muted, #64748b); font-size: 13px; line-height: 1.5; overflow-wrap: anywhere; }
.state-icon { flex-shrink: 0; }
.save-state.is-unsaved { color: var(--fb-warning-text, #925b12); }
.save-state.is-saved .state-icon { color: #67c23a; }
.write-actions { display: flex; gap: 10px; flex-shrink: 0; }
.answer-footer .el-button { height: 36px; padding: 0 18px; border-radius: 8px; font-weight: 500; }
.write-actions .el-button + .el-button { margin-left: 0; }
@media (max-width: 600px) {
  .answer-footer { bottom: calc(10px + env(safe-area-inset-bottom)); flex-direction: column; align-items: stretch; gap: 10px; margin: 16px 0 0; padding: 12px; }
  .write-actions .el-button { flex: 1; min-width: 0; padding: 0 10px; }
  .answer-header h1 { font-size: 21px; }
  .answer-question:deep(.el-slider__runway.show-input) { margin-right: 0; width: 100%; }
  .answer-question:deep(.el-slider) { flex-wrap: wrap; height: auto; gap: 16px; padding: 10px; }
}
</style>
