<script setup>
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'

import IndicatorPanel from '@/components/feedback/IndicatorPanel.vue'
import QuestionnaireOutline from '@/components/feedback/QuestionnaireOutline.vue'
import QuestionnairePreviewContent from '@/components/feedback/QuestionnairePreviewContent.vue'
import QuestionTypePanel from '@/components/feedback/QuestionTypePanel.vue'
import RichTextEditor from '@/components/feedback/RichTextEditor.vue'
import QuestionPropertiesPanel from '@/components/feedback/questions/QuestionPropertiesPanel.vue'
import QuestionCanvasCard from '@/components/feedback/questions/QuestionCanvasCard.vue'
import { getQuestionTypeDefinition } from '@/components/feedback/questions/questionTypeRegistry'
import { useQuestionnaireDraftStore } from '@/stores/questionnaireDraft'
import { usePermissionStore } from '@/stores/permission'
import { calculateRawMaxScore } from '@/utils/questionnaireDraft'

const route = useRoute()
const router = useRouter()
const draftStore = useQuestionnaireDraftStore()
const permissionStore = usePermissionStore()
const questionnaireFormRef = ref()
const questionCards = new Map()
const savePending = ref(false)
const actionMessage = ref('')
const isSaving = computed(() => savePending.value || draftStore.saving)
const activeRightTab = ref('question')
const livePreviewRef = ref()
const projectId = Number(route.params.projectId)
const draft = computed(() => draftStore.draft)
const selectedPage = computed(() => draftStore.selectedPage)
const selectedQuestion = computed(() => draftStore.selectedQuestion)
const rawMaxScore = computed(() => calculateRawMaxScore(draft.value))
const selectedPageIndex = computed(() =>
  draft.value?.pages.findIndex(page => page.pageCode === draftStore.selectedPageCode) ?? -1
)

function changeDraftField(field, value) {
  draft.value[field] = value
  draftStore.markDirty()
}

function changeDescriptionDocument(value) {
  draft.value.descriptionDoc = value
  draftStore.markDirty()
}

async function focusQuestion(questionCode, title = false) {
  await nextTick()
  const card = questionCards.get(questionCode)
  if (title) await card?.focusTitle()
  else card?.focusCard()
}

async function selectQuestion(questionCode) {
  draftStore.selectQuestion(questionCode)
  if (activeRightTab.value === 'indicator') activeRightTab.value = 'question'
  await focusQuestion(questionCode)
}

async function addQuestion(questionType) {
  if (isSaving.value) return
  const question = draftStore.addQuestion(questionType)
  if (activeRightTab.value === 'indicator') activeRightTab.value = 'question'
  if (question) await focusQuestion(question.questionCode, true)
}

async function duplicateQuestion(questionCode) {
  if (isSaving.value) return
  draftStore.selectQuestion(questionCode)
  const duplicated = draftStore.duplicateSelectedQuestion()
  actionMessage.value = '题目已复制到下一题'
  if (duplicated) await focusQuestion(duplicated.questionCode, true)
}

async function moveQuestion(questionCode, offset) {
  if (isSaving.value) return
  draftStore.selectQuestion(questionCode)
  draftStore.moveSelectedQuestion(offset)
  actionMessage.value = offset < 0 ? '题目已上移' : '题目已下移'
  await focusQuestion(questionCode)
}

async function moveQuestionToPage(pageCode) {
  if (isSaving.value) return
  draftStore.moveSelectedQuestionToPage(pageCode)
  await focusQuestion(draftStore.selectedQuestionCode)
}

async function removeQuestion(questionCode) {
  if (isSaving.value) return
  const currentDraft = draft.value
  try {
    await ElMessageBox.confirm('确认删除当前题目吗？相关指标绑定也会移除。', '删除题目', {
      type: 'warning',
      confirmButtonText: '删除题目',
      cancelButtonText: '取消'
    })
    if (draft.value !== currentDraft || isSaving.value || !draft.value.pages.some(page => page.questions.some(question => question.questionCode === questionCode))) return
    draftStore.selectQuestion(questionCode)
    draftStore.removeSelectedQuestion()
    actionMessage.value = '题目已删除'
    await focusQuestion(draftStore.selectedQuestionCode)
  } catch {
    // 用户取消时保持编辑状态。
  }
}

async function removePage(pageCode) {
  if (isSaving.value) return
  const currentDraft = draft.value
  const page = draft.value.pages.find(item => item.pageCode === pageCode)
  try {
    await ElMessageBox.confirm(
      `确认删除“${page?.pageTitle || '当前页面'}”吗？页面内题目及指标绑定会一并移除。`,
      '删除页面',
      {
        type: 'warning',
        confirmButtonText: '删除页面',
        cancelButtonText: '取消'
      }
    )
    if (draft.value === currentDraft && !isSaving.value) draftStore.removePage(pageCode)
  } catch {
    // 用户取消时保持编辑状态。
  }
}

async function saveDraft() {
  if (isSaving.value) return
  savePending.value = true
  let invalidQuestionCode = ''
  try {
    await questionnaireFormRef.value?.validate()
    const invalidQuestion = draft.value.pages.flatMap(page => page.questions)
      .find(question => getQuestionTypeDefinition(question.questionType)?.validate(question).length)
    if (invalidQuestion) {
      invalidQuestionCode = invalidQuestion.questionCode
      draftStore.selectQuestion(invalidQuestionCode)
      activeRightTab.value = 'question'
      await nextTick()
      await questionCards.get(invalidQuestionCode)?.validate()
    }
    await questionCards.get(draftStore.selectedQuestionCode)?.validate()
    const errors = draftStore.validate()
    if (errors.length) {
      ElMessage.warning(errors[0])
      return
    }
    const saved = await draftStore.save()
    if (saved.validationIssues.length) {
      ElMessage.success(`草稿已保存；仍有${saved.validationIssues.length}项发布前检查待处理`)
    } else {
      ElMessage.success('问卷草稿已保存，已满足发布前完整性检查')
    }
  } catch (error) {
    if (error?.message && !String(error.message).includes('validation')) {
      ElMessage.warning(error.message)
    }
  } finally {
    savePending.value = false
    if (invalidQuestionCode) await focusQuestion(invalidQuestionCode, true)
  }
}

onBeforeRouteLeave(async () => {
  if (!draftStore.dirty) return true
  try {
    await ElMessageBox.confirm('当前问卷有未保存修改，确认离开吗？', '离开编辑器', {
      type: 'warning',
      confirmButtonText: '离开',
      cancelButtonText: '继续编辑'
    })
    return true
  } catch {
    return false
  }
})

onMounted(() => draftStore.load(projectId))
onBeforeUnmount(() => draftStore.reset())
</script>

<template>
  <section v-loading="draftStore.loading" class="editor-page">
    <header class="editor-header workspace-page-header workspace-detail-header">
      <div class="workspace-detail-heading">
        <el-button class="workspace-detail-back" text aria-label="返回项目列表" title="返回项目列表" @click="router.push('/hr/projects')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="m10 6-6 6 6 6M4 12h16" />
          </svg>
          <span>返回</span>
        </el-button>
        <el-divider direction="vertical" class="workspace-detail-divider" />
        <div class="workspace-detail-title">
          <h1>问卷与指标设计器</h1>
          <p class="workspace-detail-project">
            <span class="workspace-detail-project-label">所属项目</span>
            <span class="workspace-detail-project-name" :title="draft?.projectName || '评价项目'">{{ draft?.projectName || '评价项目' }}</span>
          </p>
        </div>
      </div>
      <div class="editor-actions">
        <span v-if="draftStore.dirty" class="dirty-state">有未保存修改</span>
        <span v-else-if="draftStore.lastSavedAt" class="saved-state">草稿已保存</span>
        <el-button
          v-if="permissionStore.hasAnyPermission(['feedback:participant:manage', 'feedback:project:publish'])"
          :disabled="!draft || draftStore.dirty"
          @click="router.push(`/hr/projects/${projectId}/publication`)"
        >
          配置人员与发布
        </el-button>
        <el-button type="primary" :loading="isSaving" :disabled="!draft" @click="saveDraft">
          保存草稿
        </el-button>
      </div>
    </header>

    <el-alert
      title="编辑过程中可随时保存草稿；完成问卷与指标配置后，再配置参评人员并发布。"
      type="info"
      :closable="false"
      show-icon
    />

    <p class="sr-only" role="status" aria-live="polite">{{ actionMessage }}</p>
    <div v-if="draft" class="editor-grid" :class="{ 'preview-expanded': activeRightTab === 'preview' }" :inert="isSaving ? true : null">
      <aside class="left-panel editor-panel">
        <QuestionnaireOutline
          :draft="draft"
          :selected-page-code="draftStore.selectedPageCode"
          :selected-question-code="draftStore.selectedQuestionCode"
          :disabled="isSaving"
          @select-page="draftStore.selectPage"
          @select-question="selectQuestion"
          @add-page="draftStore.addPage"
          @move-page="draftStore.movePage"
          @delete-page="removePage"
          @update-page="draftStore.updatePage"
        />
        <QuestionTypePanel @add="addQuestion" />
      </aside>

      <main class="canvas-panel editor-panel">
        <el-form ref="questionnaireFormRef" :model="draft" :disabled="isSaving" label-position="top" class="questionnaire-form" scroll-to-error>
          <el-form-item
            label="问卷标题"
            prop="title"
            :rules="[{ required: true, message: '请填写问卷标题', trigger: 'blur' }]"
          >
            <el-input
              :model-value="draft.title"
              maxlength="200"
              show-word-limit
              @input="changeDraftField('title', $event)"
              @keydown.enter="!$event.isComposing && $event.preventDefault()"
            />
          </el-form-item>
          <el-form-item label="问卷说明">
            <RichTextEditor
              :model-value="draft.descriptionDoc"
              @update:model-value="changeDescriptionDocument"
            />
          </el-form-item>
        </el-form>

        <div class="canvas-summary">
          <span>{{ selectedPage?.pageTitle }} · {{ selectedPageIndex + 1 }} / {{ draft.pages.length }} 页 · {{ selectedPage?.questions.length || 0 }} 题</span>
          <span>原始满分预览：{{ rawMaxScore }}</span>
        </div>
        <el-empty
          v-if="selectedPage && !selectedPage.questions.length"
          description="从左侧题型面板添加当前页面的第一道题"
          :image-size="92"
        />
        <QuestionCanvasCard
          v-for="(question, index) in selectedPage?.questions || []"
          :key="question.questionCode"
          :ref="element => element ? questionCards.set(question.questionCode, element) : questionCards.delete(question.questionCode)"
          :question="question"
          :index="index"
          :active="question.questionCode === draftStore.selectedQuestionCode"
          :can-move-up="index > 0"
          :can-move-down="index < selectedPage.questions.length - 1"
          :disabled="isSaving"
          @select="draftStore.selectQuestion"
          @change="draftStore.updateQuestion"
          @duplicate="duplicateQuestion"
          @move="moveQuestion"
          @delete="removeQuestion"
        />
      </main>

      <aside class="right-panel editor-panel" aria-label="预览与设置">
        <el-tabs v-model="activeRightTab" stretch>
          <el-tab-pane label="实时预览" name="preview">
            <div class="live-preview-controls">
              <div class="live-preview-toolbar">
                <span>第 {{ selectedPageIndex + 1 }} / {{ draft.pages.length }} 页</span>
                <el-button link type="primary" @click="livePreviewRef?.resetAnswers()">重新试填</el-button>
              </div>
              <el-pagination
                v-if="draft.pages.length > 1"
                class="live-preview-pagination"
                aria-label="预览页码"
                :current-page="selectedPageIndex + 1"
                :page-count="draft.pages.length"
                :pager-count="5"
                :disabled="isSaving"
                layout="prev, pager, next"
                size="small"
                @update:current-page="draftStore.selectPage(draft.pages[$event - 1]?.pageCode)"
              />
              <p class="live-preview-hint">修改即时同步，试填内容不会保存。</p>
            </div>
            <QuestionnairePreviewContent
              ref="livePreviewRef"
              v-if="selectedPage"
              :draft="draft"
              :page-code="selectedPage.pageCode"
              :selected-question-code="draftStore.selectedQuestionCode"
              :active="activeRightTab === 'preview'"
              compact
            />
          </el-tab-pane>
          <el-tab-pane label="题目属性" name="question">
            <QuestionPropertiesPanel
              v-if="selectedQuestion && selectedPage"
              :question="selectedQuestion"
              :pages="draft.pages"
              :current-page-code="selectedPage.pageCode"
              :indicators="draft.indicators"
              :disabled="isSaving"
              @change="draftStore.updateQuestion"
              @move-to-page="moveQuestionToPage"
              @set-indicator="draftStore.setQuestionIndicator"
            />
            <el-empty v-else description="选择一道题后配置属性" :image-size="84" />
            <div v-if="draft.validationIssues.length" class="validation-issues">
              <strong>最近保存时的发布检查</strong>
              <ul><li v-for="issue in draft.validationIssues" :key="`${issue.code}-${issue.path}`">{{ issue.message }}</li></ul>
            </div>
          </el-tab-pane>
          <el-tab-pane label="评价指标" name="indicator">
            <IndicatorPanel
              :indicators="draft.indicators"
              :questions="draftStore.scoredQuestions"
              @add="draftStore.addIndicator"
              @change="draftStore.updateIndicator"
              @delete="draftStore.removeIndicator"
              @move="draftStore.moveIndicator"
              @set-bindings="draftStore.setIndicatorBindings"
            />
          </el-tab-pane>
        </el-tabs>
      </aside>
    </div>

  </section>
</template>

<style scoped>
.editor-page { display: grid; gap: 16px; min-height: calc(100vh - 120px); }
.editor-actions, .canvas-summary, .page-heading { display: flex; align-items: center; justify-content: space-between; gap: 14px; }
.editor-actions { flex-shrink: 0; flex-wrap: wrap; justify-content: flex-end; gap: 10px; }
.editor-actions :deep(.el-button + .el-button) { margin-left: 0; }
.dirty-state { color: #e6a23c; font-size: 13px; }
.saved-state { color: #67c23a; font-size: 13px; }
.editor-grid { display: grid; grid-template-columns: 210px minmax(360px, 1fr) 390px; gap: 14px; align-items: start; }
.editor-grid.preview-expanded { grid-template-columns: 210px minmax(360px, 1fr) clamp(390px, 40%, 760px); }
.editor-panel { min-width: 0; padding: 18px; border: 1px solid #e5e7eb; border-radius: 10px; background: #fff; }
.left-panel, .right-panel { position: sticky; top: var(--workspace-panel-top, 78px); max-height: calc(100vh - var(--workspace-panel-top, 78px) - 22px); overflow-y: auto; }
.left-panel { display: grid; gap: 24px; }
.left-panel > * { min-width: 0; }
.right-panel { height: calc(100vh - var(--workspace-panel-top, 78px) - 22px); display: flex; padding: 0; overflow: hidden; }
.right-panel :deep(.el-tabs) { display: flex; flex-direction: column; min-width: 0; width: 100%; }
.right-panel :deep(.el-tabs__header) { flex: none; margin: 0; padding: 10px 14px 0; }
.right-panel :deep(.el-tabs__content) { flex: 1; overflow-y: auto; min-height: 0; padding: 14px; }
.editor-grid.preview-expanded .right-panel :deep(.el-tabs__content) { --preview-gutter: clamp(14px, 1vw, 22px); padding: var(--preview-gutter); background: #e7ecef; }
.live-preview-controls { margin: calc(-1 * var(--preview-gutter, 14px)) calc(-1 * var(--preview-gutter, 14px)) 20px; padding: 12px var(--preview-gutter, 14px); border-bottom: 1px solid #dce1e6; background: #fff; }
.live-preview-toolbar { display: flex; justify-content: space-between; align-items: center; gap: 8px; font-size: 12px; color: #606266; }
.live-preview-pagination { justify-content: center; margin-top: 8px; }
.live-preview-hint { margin: 6px 0 0; color: #909399; font-size: 12px; }
.questionnaire-form { padding-bottom: 4px; border-bottom: 1px solid #e5e7eb; }
.page-heading { margin-bottom: 14px; color: #64748b; font-size: 13px; }
.canvas-summary { margin: 10px 0; color: #64748b; font-size: 13px; }
.sr-only { position: absolute; width: 1px; height: 1px; margin: -1px; overflow: hidden; clip-path: inset(50%); }
.validation-issues { margin-top: 16px; padding: 12px; border-radius: 8px; color: #b45309; background: #fff7ed; font-size: 13px; }
.validation-issues ul { margin: 8px 0 0; padding-left: 20px; }
@media (max-width: 1500px) {
  .editor-grid { grid-template-columns: 190px minmax(340px, 1fr) 330px; gap: 12px; }
  .editor-grid.preview-expanded { grid-template-columns: 190px minmax(340px, 1fr) clamp(330px, 40%, calc(100% - 554px)); }
  .editor-panel { padding: 14px; }
  .right-panel { padding: 0; }
}
@media (max-width: 1100px) {
  .editor-grid { grid-template-columns: minmax(340px, 1fr) 320px; }
  .editor-grid.preview-expanded { grid-template-columns: minmax(340px, 1fr) clamp(320px, 44%, calc(100% - 352px)); }
  .left-panel { grid-column: 1 / -1; position: static; max-height: none; grid-template-columns: 1fr 1fr; }
}
@media (max-width: 760px) {
  .editor-header, .editor-actions { align-items: flex-start; flex-wrap: wrap; }
  .editor-grid, .editor-grid.preview-expanded { grid-template-columns: 1fr; }
  .left-panel, .right-panel { position: static; max-height: none; }
  .left-panel { grid-template-columns: 1fr; }
  .right-panel { height: auto; min-height: 380px; }
}
@media (max-width: 760px) {
  .editor-actions { width: 100%; justify-content: flex-start; }
  .editor-actions .dirty-state, .editor-actions .saved-state { flex-basis: 100%; }
}
</style>
