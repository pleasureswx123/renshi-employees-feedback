<script setup>
import ChevronsRightIcon from '@iconify-vue/lucide/chevrons-right'
import ChevronsLeftIcon from '@iconify-vue/lucide/chevrons-left'
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
import { getQuestionnaireWorkflow } from '@/utils/questionnaireWorkflow'

const route = useRoute()
const router = useRouter()
const draftStore = useQuestionnaireDraftStore()
const permissionStore = usePermissionStore()
const questionnaireFormRef = ref()
const questionnaireInfoOpen = ref(['info'])
const questionCards = new Map()
const savePending = ref(false)
const advancing = ref(false)
const actionMessage = ref('')
const isSaving = computed(() => savePending.value || draftStore.saving)
const activeRightTab = ref('question')
const rightPanelOpen = ref(false)
const leftPanelOpen = ref(true)
const activeLeftTab = ref('types')
function toggleLeftPanel(tab) {
  const name = tab.paneName
  leftPanelOpen.value = !leftPanelOpen.value || activeLeftTab.value !== name
  activeLeftTab.value = name
}
function toggleRightPanel(tab) {
  const name = tab.paneName
  rightPanelOpen.value = !rightPanelOpen.value || activeRightTab.value !== name
  activeRightTab.value = name
}
const livePreviewRef = ref()
const projectId = Number(route.params.projectId)
const draft = computed(() => draftStore.draft)
const selectedPage = computed(() => draftStore.selectedPage)
const selectedQuestion = computed(() => draftStore.selectedQuestion)
const rawMaxScore = computed(() => calculateRawMaxScore(draft.value))
const rawMaxScoreLabel = computed(() => String(rawMaxScore.value).replace(/(\.\d*?[1-9])0+$|\.0+$/, '$1'))
const selectedQuestionNumber = computed(() => (draft.value?.pages.flatMap(page => page.questions)
  .findIndex(question => question.questionCode === draftStore.selectedQuestionCode) ?? -1) + 1)

async function validateQuestionnaireInfo() {
  if (!draft.value?.title?.trim()) {
    questionnaireInfoOpen.value = ['info']
    await nextTick()
  }
  await questionnaireFormRef.value?.validate()
}
const selectedPageIndex = computed(() =>
  draft.value?.pages.findIndex(page => page.pageCode === draftStore.selectedPageCode) ?? -1
)
const workflow = computed(() => getQuestionnaireWorkflow(draft.value))
const workflowHint = computed(() => {
  if (!workflow.value.questionReady) return workflow.value.questionIssues[0]
  if (activeRightTab.value !== 'indicator') return '问卷已完成，下一步设置指标权重与题目绑定'
  if (!workflow.value.indicatorReady) return workflow.value.indicatorIssues[0]
  return '指标已完成，下一步保存并配置参评人员'
})

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
    await validateQuestionnaireInfo()
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
    return saved
  } catch (error) {
    if (error?.message && !String(error.message).includes('validation')) {
      ElMessage.warning(error.message)
    }
  } finally {
    savePending.value = false
    if (invalidQuestionCode) await focusQuestion(invalidQuestionCode, true)
  }
}

async function nextStep() {
  if (!draft.value || isSaving.value || advancing.value) return
  if (!workflow.value.questionReady) {
    activeRightTab.value = 'question'
    ElMessage.warning(workflow.value.questionIssues[0])
    try {
      await validateQuestionnaireInfo()
      const code = workflow.value.invalidQuestionCode
      if (code) {
        draftStore.selectQuestion(code)
        await focusQuestion(code, true)
        await questionCards.get(code)?.validate()
      }
    } catch {
      // 保留原有表单校验反馈，完成题目后再进入指标步骤。
    }
    return
  }
  if (activeRightTab.value !== 'indicator') {
    activeRightTab.value = 'indicator'
    rightPanelOpen.value = true
    return
  }
  if (!workflow.value.indicatorReady) {
    rightPanelOpen.value = true
    ElMessage.warning(workflow.value.indicatorIssues[0])
    return
  }
  if (!permissionStore.hasAnyPermission(['feedback:participant:manage', 'feedback:project:publish'])) return
  advancing.value = true
  try {
    const saved = await saveDraft()
    if (!saved) return
    if (!saved.isPublishReady || saved.validationIssues.length) {
      ElMessage.warning(saved.validationIssues[0]?.message || '请完成问卷与指标的发布前检查')
      return
    }
    await router.push(`/hr/projects/${projectId}/publication`)
  } finally {
    advancing.value = false
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
        <el-button class="workspace-detail-back" text size="small" aria-label="返回项目列表" title="返回项目列表" @click="router.push('/hr/projects')">
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
        <el-tooltip content="先完成问卷，再设置指标；两步检查通过后，保存并进入人员配置。" :trigger="['hover', 'focus']" :trigger-keys="[]">
          <el-button class="editor-help" text circle size="small" aria-label="编辑流程说明">?</el-button>
        </el-tooltip>
      </div>
      <div class="editor-actions">
        <span v-if="draftStore.dirty" class="dirty-state">有未保存修改</span>
        <span v-else-if="draftStore.lastSavedAt" class="saved-state">草稿已保存</span>
        <span v-else class="saved-state">未修改</span>
        <el-button
          :disabled="!draft || isSaving || advancing"
          @click="saveDraft"
        >
          保存草稿
        </el-button>
        <el-button
          v-if="!workflow.questionReady || activeRightTab !== 'indicator' || permissionStore.hasAnyPermission(['feedback:participant:manage', 'feedback:project:publish'])"
          type="primary"
          :loading="advancing"
          :disabled="!draft || isSaving"
          @click="nextStep"
        >
          {{ !workflow.questionReady ? '完善问卷' : activeRightTab === 'indicator' ? '下一步：配置人员' : '下一步：配置指标' }}
        </el-button>
      </div>
    </header>

    <div class="editor-workflow" aria-label="评价准备流程">
      <el-steps :active="workflow.questionReady && activeRightTab === 'indicator' ? 1 : 0" simple finish-status="success">
        <el-step :title="workflow.questionReady && activeRightTab === 'indicator' ? '1 编辑问卷 · 已检查' : '1 编辑问卷 · 当前'" :status="workflow.questionReady && activeRightTab === 'indicator' ? 'success' : 'process'" />
        <el-step :title="workflow.questionReady && activeRightTab === 'indicator' ? '2 配置指标 · 当前' : '2 配置指标'" :status="workflow.questionReady && activeRightTab === 'indicator' ? 'process' : 'wait'" />
        <el-step title="3 人员与发布" />
      </el-steps>
      <p class="workflow-hint" role="status" aria-live="polite" :title="workflowHint">{{ workflowHint }}</p>
    </div>

    <p class="sr-only" role="status" aria-live="polite">{{ actionMessage }}</p>
    <div v-if="draft" :key="projectId" class="editor-grid" :class="{ 'preview-expanded': rightPanelOpen && activeRightTab === 'preview', 'right-collapsed': !rightPanelOpen, 'left-collapsed': !leftPanelOpen }" :inert="isSaving ? true : null">
      <aside class="left-panel editor-panel" aria-label="题型与大纲">
        <div class="panel-toggle-bar">
          <el-button class="collapse-panel-button" text :aria-label="leftPanelOpen ? '收起左侧面板' : '展开左侧面板'" :title="leftPanelOpen ? '收起左侧面板' : '展开左侧面板'" :aria-expanded="leftPanelOpen" @click="leftPanelOpen = !leftPanelOpen">
            <ChevronsLeftIcon v-if="leftPanelOpen" aria-hidden="true" />
            <ChevronsRightIcon v-else aria-hidden="true" />
          </el-button>
        </div>
        <el-tabs :model-value="activeLeftTab" tab-position="left" @tab-click="toggleLeftPanel">
          <el-tab-pane label="题型面板" name="types"><QuestionTypePanel @add="addQuestion" /></el-tab-pane>
          <el-tab-pane label="问卷大纲" name="outline">
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
        />
          </el-tab-pane>
        </el-tabs>
      </aside>

      <main class="canvas-panel editor-panel">
        <el-collapse v-model="questionnaireInfoOpen" class="questionnaire-info">
        <el-collapse-item name="info">
          <template #title><span class="info-title">问卷信息</span><span class="info-summary">{{ draft.title || '填写问卷标题与说明' }}</span></template>
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
        </el-collapse-item>
        </el-collapse>

        <div class="canvas-summary">
          <span>{{ selectedPage?.pageTitle }} · {{ selectedPageIndex + 1 }} / {{ draft.pages.length }} 页 · {{ selectedPage?.questions.length || 0 }} 题</span>
          <span>原始满分预览：{{ rawMaxScoreLabel }}</span>
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
          :index="draft.pages.slice(0, selectedPageIndex).reduce((count, page) => count + page.questions.length, 0) + index"
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
        <div class="panel-toggle-bar">
          <el-button class="collapse-panel-button" text :aria-label="rightPanelOpen ? '收起右侧面板' : '展开右侧面板'" :title="rightPanelOpen ? '收起右侧面板' : '展开右侧面板'" :aria-expanded="rightPanelOpen" @click="rightPanelOpen = !rightPanelOpen">
            <ChevronsRightIcon v-if="rightPanelOpen" aria-hidden="true" />
            <ChevronsLeftIcon v-else aria-hidden="true" />
          </el-button>
        </div>
        <el-tabs :model-value="activeRightTab" tab-position="right" @tab-click="toggleRightPanel">
          <el-tab-pane label="题目属性" name="question">
            <QuestionPropertiesPanel
              :question-number="selectedQuestionNumber"
              v-if="selectedQuestion && selectedPage"
              :question="selectedQuestion"
              :pages="draft.pages"
              :current-page-code="selectedPage.pageCode"
              :disabled="isSaving"
              @change="draftStore.updateQuestion"
              @move-to-page="moveQuestionToPage"
            />
            <el-empty v-else description="选择一道题后配置属性" :image-size="84" />
          </el-tab-pane>
          <el-tab-pane label="评价指标" name="indicator">
            <div v-if="!workflow.questionReady" class="indicator-step-notice">
              <span>请先完成问卷，再配置指标。已有指标配置会保留。</span>
              <el-button link type="primary" size="small" @click="nextStep">返回完善问卷</el-button>
            </div>
            <div v-else-if="workflow.indicatorIssues.length" class="indicator-step-notice">
              <strong>完成以下配置即可进入人员配置</strong>
              <ul><li v-for="issue in workflow.indicatorIssues" :key="issue">{{ issue }}</li></ul>
            </div>
            <div v-else-if="!draftStore.dirty && draft.validationIssues.length" class="indicator-step-notice">
              <strong>保存检查发现以下问题</strong>
              <ul><li v-for="issue in draft.validationIssues" :key="`${issue.code}-${issue.path}`">{{ issue.message }}</li></ul>
            </div>
            <IndicatorPanel
              v-if="workflow.questionReady"
              :indicators="draft.indicators"
              :questions="draftStore.scoredQuestions"
              :pages="draft.pages"
              @add="draftStore.addIndicator"
              @change="draftStore.updateIndicator"
              @delete="draftStore.removeIndicator"
              @move="draftStore.moveIndicator"
              @set-bindings="draftStore.setIndicatorBindings"
              @set-question-indicator="draftStore.setQuestionIndicator"
              @locate-question="draftStore.selectQuestion($event); focusQuestion($event)"
            />
          </el-tab-pane>
          <el-tab-pane label="实时预览" name="preview">
            <div class="live-preview-controls">
              <div class="live-preview-toolbar">
                <span class="preview-page-status">第 {{ selectedPageIndex + 1 }} / {{ draft.pages.length }} 页</span>
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
                <el-button link size="small" type="primary" @click="livePreviewRef?.resetAnswers()">重新试填</el-button>
              </div>
            </div>
            <QuestionnairePreviewContent
              ref="livePreviewRef"
              v-if="selectedPage"
              :draft="draft"
              :page-code="selectedPage.pageCode"
              :selected-question-code="draftStore.selectedQuestionCode"
              :active="rightPanelOpen && activeRightTab === 'preview'"
              compact
            />
          </el-tab-pane>
        </el-tabs>
      </aside>
    </div>

  </section>
</template>

<style scoped>
.editor-page { display: grid; grid-template-columns: minmax(0, 1fr); grid-template-rows: auto auto minmax(0, 1fr); gap: 10px; height: 100%; min-height: 0; }
.editor-workflow { display: flex; align-items: center; gap: 16px; min-width: 0; padding: 8px 14px; border: 1px solid var(--fb-border, #e5e7eb); border-radius: 8px; background: var(--fb-surface, #fff); }
.editor-workflow:deep(.el-steps) { flex: 1; min-width: 0; padding: 0; background: transparent; }
.editor-workflow:deep(.el-step__title) { font-size: 13px; white-space: nowrap; }
.editor-workflow:deep(.el-step__arrow) { flex: 1; min-width: 22px; }
.workflow-hint { flex: 0 1 330px; min-width: 0; margin: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--fb-text-muted, #73767a); font-size: 12px; }
.indicator-step-notice { margin-bottom: 12px; padding: 10px; border-radius: 6px; background: var(--fb-primary-bg, #f4f8ff); color: var(--fb-text-regular, #606266); font-size: 12px; line-height: 1.7; }
.indicator-step-notice ul { margin: 6px 0 0; padding-left: 16px; }
.editor-header { flex-wrap: nowrap; gap: 12px; padding: 10px 14px; }
.editor-header .workspace-detail-heading { flex: 1; }
.editor-header .workspace-detail-back { height: 30px; padding: 4px 6px; }
.editor-header .workspace-detail-divider { height: 26px; margin-inline: 10px; }
.editor-header .workspace-detail-title { display: flex; flex: 0 1 auto; align-items: center; gap: 14px; }
.editor-header h1 { flex: none; font-size: 17px; }
.editor-header .workspace-detail-project { min-width: 0; margin: 0; }
.editor-help { flex: none; margin-left: 8px; color: var(--fb-text-muted, #909399); }
.editor-actions, .canvas-summary, .page-heading { display: flex; align-items: center; justify-content: space-between; gap: 14px; }
.editor-actions { flex-shrink: 0; flex-wrap: wrap; justify-content: flex-end; gap: 10px; }
.editor-actions:deep(.el-button + .el-button) { margin-left: 0; }
.dirty-state { color: #e6a23c; font-size: 13px; }
.saved-state { color: #67c23a; font-size: 13px; }
.editor-grid { display: grid; grid-template-columns: var(--editor-left-width, 220px) minmax(360px, 1fr) 330px; gap: 16px; min-height: 0; align-items: stretch; }
.editor-grid.preview-expanded { grid-template-columns: var(--editor-left-width, 210px) minmax(360px, 1fr) clamp(390px, 40%, 760px); }
.editor-panel { min-width: 0; padding: 18px; border: 1px solid var(--fb-border, #e5e7eb); border-radius: 10px; background: var(--fb-surface, #fff); }
.left-panel, .right-panel, .canvas-panel { min-height: 0; overflow-y: auto; overscroll-behavior: contain; }
.left-panel { display: flex; flex-direction: column; padding: 0; overflow: hidden; }
.left-panel > * { min-width: 0; }

.right-panel { position: relative; display: flex; flex-direction: column; padding: 0; overflow: hidden; }
:is(.left-panel, .right-panel):deep(.el-tabs) { display: flex; flex: 1; flex-direction: row; min-height: 0; min-width: 0; width: 100%; }
:is(.left-panel, .right-panel):deep(.el-tabs__header) { order: 1; flex: 0 0 32px; width: 32px; margin: 0; padding: 0; box-sizing: border-box; float: none; }
.panel-toggle-bar { display: flex; justify-content: flex-end; flex: 0 0 22px; height: 22px; box-sizing: border-box; border-bottom: 1px solid var(--fb-border, #e5e7eb); background: var(--el-fill-color-light); }
.collapse-panel-button { width: 32px; height: 21px; padding: 5px; border-radius: 0; color: var(--el-text-color-secondary); }
.collapse-panel-button:hover { color: var(--el-color-primary); }
.collapse-panel-button svg { width: 12px; height: 12px; }
:is(.left-panel, .right-panel):deep(.el-tabs__nav-wrap) { margin: 0; }
:is(.left-panel, .right-panel):deep(.el-tabs__item) { width: 32px; height: 96px; padding: 12px 8px; font-size: 12px; writing-mode: vertical-rl; letter-spacing: 2px; justify-content: center; border-bottom: 1px solid var(--fb-border, #e5e7eb); }
:is(.left-panel, .right-panel):deep(.el-tabs__item.is-active) { background: var(--fb-primary-bg, #ecf5ff); }
:is(.left-panel, .right-panel):deep(.el-tabs__content) { flex: 1; min-width: 0; overflow-y: auto; min-height: 0; padding: 14px; }
.editor-grid.preview-expanded .right-panel:deep(.el-tabs__content) { --preview-gutter: clamp(14px, 1vw, 22px); padding: var(--preview-gutter); background: var(--fb-surface-muted, #e7ecef); }
.live-preview-controls { position: sticky; top: calc(-1 * var(--preview-gutter, 14px)); z-index: 2; margin: calc(-1 * var(--preview-gutter, 14px)) calc(-1 * var(--preview-gutter, 14px)) 16px; padding: 10px var(--preview-gutter, 14px); border-bottom: 1px solid var(--fb-border, #dce1e6); background: var(--fb-surface, #fff); }
.live-preview-toolbar { display: flex; justify-content: space-between; align-items: center; gap: 6px; font-size: 12px; color: var(--fb-text-regular, #606266); }
.preview-page-status, .live-preview-toolbar > .el-button { flex: none; white-space: nowrap; }
.live-preview-pagination { flex: 1; min-width: 0; margin: 0; }
.live-preview-toolbar:deep(.el-pagination) { justify-content: center; }
.live-preview-pagination:deep(.number), .live-preview-pagination :deep(.btn-prev), .live-preview-pagination :deep(.btn-next), .live-preview-pagination :deep(.more) { min-width: 22px; margin-inline: 0; }
.questionnaire-form { padding: 12px 0 0; }
.questionnaire-info { border-top: 0; }
.questionnaire-info:deep(.el-collapse-item__header) { gap: 12px; background: transparent; }
.questionnaire-info:deep(.el-collapse-item__content) { padding-bottom: 0; }
.info-title { flex: none; margin-right: 12px; font-size: 14px; font-weight: 600; }
.info-summary { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--fb-text-muted, #73767a); font-size: 13px; }
.dirty-state, .saved-state { width: 100px; text-align: right; }
.page-heading { margin-bottom: 14px; color: var(--fb-text-muted, #64748b); font-size: 13px; }
.canvas-summary { flex-wrap: wrap; gap: 8px 12px; margin: 10px 0; color: var(--fb-text-muted, #64748b); font-size: 13px; }
.canvas-summary > span:first-child { min-width: 0; overflow-wrap: anywhere; }
.canvas-summary > span:last-child { flex: none; margin-left: auto; padding: 5px 0; color: var(--fb-text-muted, #64748b); font-size: 13px; font-weight: 500; font-variant-numeric: tabular-nums; line-height: 22px; white-space: nowrap; }
.sr-only { position: absolute; width: 1px; height: 1px; margin: -1px; overflow: hidden; clip-path: inset(50%); }
.validation-issues { margin-top: 16px; padding: 10px 12px; border: 1px solid var(--fb-warning-border, #fae4c5); border-radius: 6px; color: var(--fb-warning-text, #a65c16); background: var(--fb-warning-bg, #fffbf5); font-size: 12px; line-height: 1.6; overflow-wrap: anywhere; }
.validation-issues strong { font-weight: 600; }
.validation-issues ul { margin: 6px 0 0; padding-left: 16px; }
.validation-issues li + li { margin-top: 4px; }
@media (max-width: 1500px) {
  .editor-grid { grid-template-columns: var(--editor-left-width, 200px) minmax(340px, 1fr) 300px; gap: 12px; }
  .editor-grid.preview-expanded { grid-template-columns: var(--editor-left-width, 190px) minmax(340px, 1fr) clamp(330px, 40%, calc(100% - 554px)); }
  .editor-panel { padding: 14px; }
  .left-panel, .right-panel { padding: 0; }
}
@media (max-width: 1100px) {
  .editor-workflow { flex-wrap: wrap; gap: 4px; }
  .editor-workflow:deep(.el-steps) { flex-basis: 100%; }
  .workflow-hint { flex-basis: 100%; }
  .editor-grid, .editor-grid.preview-expanded { grid-template-columns: var(--editor-left-width, 160px) minmax(260px, 1fr) 300px; gap: 10px; overflow-x: auto; }
  .editor-header .workspace-detail-title { display: block; }
  .editor-header .workspace-detail-project { margin-top: 2px; }
  .editor-actions { gap: 6px; }
}
@media (max-width: 760px) {
  .editor-page { height: auto; grid-template-rows: auto auto auto; }
  .editor-workflow { padding: 8px; }
  .editor-workflow:deep(.el-step__title) { font-size: 11px; }
  .editor-workflow:deep(.el-step__head) { display: none; }
  .editor-header, .editor-actions { align-items: flex-start; flex-wrap: wrap; }
  .editor-grid, .editor-grid.preview-expanded { grid-template-columns: 1fr; }
  .left-panel, .right-panel { position: static; max-height: none; }
  .left-panel { max-height: 560px; }
  .left-panel > .questionnaire-outline { flex-basis: 280px; }
  .right-panel { height: auto; min-height: 380px; }
}
@media (max-width: 760px) {
  .editor-actions { width: 100%; justify-content: flex-start; }
  .editor-actions .dirty-state, .editor-actions .saved-state { flex-basis: 100%; }
}
.editor-grid.right-collapsed { grid-template-columns: var(--editor-left-width, 220px) minmax(360px, 1fr) 34px; }
.right-collapsed .right-panel:deep(.el-tabs__content) { display: none; }
.right-collapsed .right-panel:deep(.el-tabs__item.is-active) { color: var(--fb-text-regular, #606266); background: transparent; }
:is(.left-panel, .right-panel):deep(.el-tabs__active-bar) { width: 1px; background-color: #a8b8c8; }
:is(.left-panel, .right-panel):deep(.el-tabs__nav-wrap::after) { width: 1px; }
.right-collapsed .right-panel:deep(.el-tabs__active-bar),
.left-collapsed .left-panel:deep(.el-tabs__active-bar) { display: none; }
@media (max-width: 1500px) { .editor-grid.right-collapsed { grid-template-columns: var(--editor-left-width, 200px) minmax(340px, 1fr) 34px; } }
@media (max-width: 1100px) { .editor-grid.right-collapsed { grid-template-columns: var(--editor-left-width, 160px) minmax(260px, 1fr) 34px; } }
@media (max-width: 760px) {
  .editor-grid.right-collapsed { grid-template-columns: minmax(0, 1fr) 34px; }
  .right-collapsed .left-panel { grid-column: 1 / -1; }
  .right-collapsed .right-panel { grid-column: 2; grid-row: 2; }
}
.left-panel :deep(.el-tabs__header) { order: -1; }
.left-panel .panel-toggle-bar { justify-content: flex-start; }
.left-panel :deep(.el-tabs__content) { padding: 0; }
.left-panel :deep(#pane-types) { padding: 10px; }
.left-panel :deep(#pane-outline) { height: 100%; }
.left-panel :deep(.questionnaire-outline) { height: 100%; min-height: 0; }
.editor-grid.left-collapsed { --editor-left-width: 34px; }
.left-collapsed .left-panel :deep(.el-tabs__content) { display: none; }
.left-collapsed .left-panel :deep(.el-tabs__item.is-active) { color: var(--fb-text-regular, #606266); background: transparent; }
@media (max-width: 760px) { .left-panel { min-height: 300px; } }
</style>
