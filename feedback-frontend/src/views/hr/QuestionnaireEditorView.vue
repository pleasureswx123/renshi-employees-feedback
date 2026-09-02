<script setup>
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'

import IndicatorPanel from '@/components/feedback/IndicatorPanel.vue'
import QuestionnaireOutline from '@/components/feedback/QuestionnaireOutline.vue'
import QuestionnairePreviewDialog from '@/components/feedback/QuestionnairePreviewDialog.vue'
import QuestionTypePanel from '@/components/feedback/QuestionTypePanel.vue'
import RichTextEditor from '@/components/feedback/RichTextEditor.vue'
import QuestionPropertiesPanel from '@/components/feedback/questions/QuestionPropertiesPanel.vue'
import QuestionRenderer from '@/components/feedback/questions/QuestionRenderer.vue'
import { getQuestionTypeDefinition } from '@/components/feedback/questions/questionTypeRegistry'
import { useQuestionnaireDraftStore } from '@/stores/questionnaireDraft'
import { usePermissionStore } from '@/stores/permission'
import { calculateRawMaxScore } from '@/utils/questionnaireDraft'

const route = useRoute()
const router = useRouter()
const draftStore = useQuestionnaireDraftStore()
const permissionStore = usePermissionStore()
const questionnaireFormRef = ref()
const propertiesRef = ref()
const previewVisible = ref(false)
const activeRightTab = ref('question')
const projectId = Number(route.params.projectId)
const draft = computed(() => draftStore.draft)
const selectedPage = computed(() => draftStore.selectedPage)
const selectedQuestion = computed(() => draftStore.selectedQuestion)
const selectedQuestionIndex = computed(() =>
  selectedPage.value?.questions.findIndex(
    question => question.questionCode === draftStore.selectedQuestionCode
  ) ?? -1
)
const canMoveSelectedQuestionUp = computed(() => selectedQuestionIndex.value > 0)
const canMoveSelectedQuestionDown = computed(() => {
  const count = selectedPage.value?.questions.length || 0
  return selectedQuestionIndex.value >= 0 && selectedQuestionIndex.value < count - 1
})
const rawMaxScore = computed(() => calculateRawMaxScore(draft.value))
const selectedPageIndex = computed(() =>
  draft.value?.pages.findIndex(page => page.pageCode === draftStore.selectedPageCode) ?? -1
)

function questionTypeLabel(questionType) {
  return getQuestionTypeDefinition(questionType)?.label || questionType
}

function changeDraftField(field, value) {
  draft.value[field] = value
  draftStore.markDirty()
}

function changeDescriptionDocument(value) {
  draft.value.descriptionDoc = value
  draftStore.markDirty()
}

function updateSelectedPage(patch) {
  if (selectedPage.value) draftStore.updatePage(selectedPage.value.pageCode, patch)
}

function addQuestion(questionType) {
  draftStore.addQuestion(questionType)
  activeRightTab.value = 'question'
}

async function removeSelectedQuestion() {
  try {
    await ElMessageBox.confirm('确认删除当前题目吗？相关指标绑定也会移除。', '删除题目', {
      type: 'warning',
      confirmButtonText: '删除题目',
      cancelButtonText: '取消'
    })
    draftStore.removeSelectedQuestion()
  } catch {
    // 用户取消时保持编辑状态。
  }
}

async function removePage(pageCode) {
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
    draftStore.removePage(pageCode)
  } catch {
    // 用户取消时保持编辑状态。
  }
}

async function saveDraft() {
  if (draftStore.saving) return
  try {
    await questionnaireFormRef.value?.validate()
    await propertiesRef.value?.validate?.()
    const errors = draftStore.validate()
    if (errors.length) {
      ElMessage.warning(errors[0])
      return
    }
    const saved = await draftStore.save()
    if (saved.validationIssues.length) {
      ElMessage.success(`草稿已保存；仍有${saved.validationIssues.length}项发布前检查待处理`)
    } else {
      ElMessage.success('问卷草稿已保存到 PostgreSQL，已满足发布前完整性检查')
    }
  } catch (error) {
    if (error?.message && !String(error.message).includes('validation')) {
      ElMessage.warning(error.message)
    }
  }
}

function openPreview() {
  const errors = draftStore.validate()
  if (errors.length) {
    ElMessage.warning(errors[0])
    return
  }
  previewVisible.value = true
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
    <header class="editor-header">
      <div class="editor-heading">
        <el-button link @click="router.push('/hr/projects')">返回项目列表</el-button>
        <div>
          <p>{{ draft?.projectName || '评价项目' }}</p>
          <h1>问卷与指标设计器</h1>
        </div>
      </div>
      <div class="editor-actions">
        <span v-if="draftStore.dirty" class="dirty-state">有未保存修改</span>
        <span v-else-if="draftStore.lastSavedAt" class="saved-state">草稿已保存</span>
        <el-button :disabled="!draft" @click="openPreview">电脑 / 手机预览</el-button>
        <el-button
          v-if="permissionStore.hasAnyPermission(['feedback:participant:manage', 'feedback:project:publish'])"
          :disabled="!draft || draftStore.dirty"
          @click="router.push(`/hr/projects/${projectId}/publication`)"
        >
          配置人员与发布
        </el-button>
        <el-button type="primary" :loading="draftStore.saving" :disabled="!draft" @click="saveDraft">
          保存草稿
        </el-button>
      </div>
    </header>

    <el-alert
      title="保存草稿允许问卷尚未达到发布条件；后端会返回权威的发布前检查结果。"
      type="info"
      :closable="false"
      show-icon
    />

    <div v-if="draft" class="editor-grid">
      <aside class="left-panel editor-panel">
        <QuestionnaireOutline
          :draft="draft"
          :selected-page-code="draftStore.selectedPageCode"
          :selected-question-code="draftStore.selectedQuestionCode"
          @select-page="draftStore.selectPage"
          @select-question="draftStore.selectQuestion"
          @add-page="draftStore.addPage"
          @move-page="draftStore.movePage"
          @delete-page="removePage"
        />
        <QuestionTypePanel @add="addQuestion" />
      </aside>

      <main class="canvas-panel editor-panel">
        <el-form ref="questionnaireFormRef" :model="draft" label-position="top" class="questionnaire-form">
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
            />
          </el-form-item>
          <el-form-item label="问卷说明（受限富文本）">
            <RichTextEditor
              :model-value="draft.descriptionDoc"
              @update:model-value="changeDescriptionDocument"
            />
          </el-form-item>
          <template v-if="selectedPage">
            <div class="page-heading">
              <strong>当前页面 {{ selectedPageIndex + 1 }} / {{ draft.pages.length }}</strong>
              <span>{{ selectedPage.questions.length }}题</span>
            </div>
            <el-form-item
              label="页面标题"
              :prop="`pages.${selectedPageIndex}.pageTitle`"
              :rules="[{ required: true, message: '请填写页面标题', trigger: 'blur' }]"
            >
              <el-input
                :model-value="selectedPage.pageTitle"
                maxlength="200"
                @input="updateSelectedPage({ pageTitle: $event })"
              />
            </el-form-item>
            <el-form-item label="页面说明">
              <el-input
                :model-value="selectedPage.pageDescription"
                type="textarea"
                :rows="2"
                maxlength="5000"
                @input="updateSelectedPage({ pageDescription: $event })"
              />
            </el-form-item>
          </template>
        </el-form>

        <div class="canvas-summary">
          <span>题目画布</span>
          <span>原始满分预览：{{ rawMaxScore }}</span>
        </div>
        <el-empty
          v-if="selectedPage && !selectedPage.questions.length"
          description="从左侧题型面板添加当前页面的第一道题"
          :image-size="92"
        />
        <article
          v-for="(question, index) in selectedPage?.questions || []"
          :key="question.questionCode"
          :class="['question-card', { active: question.questionCode === draftStore.selectedQuestionCode }]"
          @click="draftStore.selectQuestion(question.questionCode)"
        >
          <div class="question-index">第 {{ index + 1 }} 题 · {{ questionTypeLabel(question.questionType) }}</div>
          <QuestionRenderer :question="question" mode="editor" />
        </article>
      </main>

      <aside class="right-panel editor-panel">
        <el-tabs v-model="activeRightTab" stretch>
          <el-tab-pane label="题目属性" name="question">
            <QuestionPropertiesPanel
              v-if="selectedQuestion && selectedPage"
              ref="propertiesRef"
              :question="selectedQuestion"
              :pages="draft.pages"
              :current-page-code="selectedPage.pageCode"
              :can-move-up="canMoveSelectedQuestionUp"
              :can-move-down="canMoveSelectedQuestionDown"
              @change="draftStore.updateQuestion"
              @duplicate="draftStore.duplicateSelectedQuestion"
              @move-up="draftStore.moveSelectedQuestion(-1)"
              @move-down="draftStore.moveSelectedQuestion(1)"
              @move-to-page="draftStore.moveSelectedQuestionToPage"
              @delete="removeSelectedQuestion"
            />
            <el-empty v-else description="选择一道题后配置属性" :image-size="84" />
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
        <div v-if="draft.validationIssues.length" class="validation-issues">
          <strong>发布前仍需处理</strong>
          <ul><li v-for="issue in draft.validationIssues" :key="`${issue.code}-${issue.path}`">{{ issue.message }}</li></ul>
        </div>
      </aside>
    </div>

    <QuestionnairePreviewDialog v-model="previewVisible" :draft="draft" />
  </section>
</template>

<style scoped>
.editor-page { display: grid; gap: 16px; min-height: calc(100vh - 120px); }
.editor-header, .editor-heading, .editor-actions, .canvas-summary, .page-heading { display: flex; align-items: center; justify-content: space-between; gap: 14px; }
.editor-heading { justify-content: flex-start; }
.editor-heading p, .editor-heading h1 { margin: 0; }
.editor-heading p { margin-bottom: 3px; color: #64748b; font-size: 13px; }
.editor-heading h1 { color: #111827; font-size: 22px; }
.dirty-state { color: #e6a23c; font-size: 13px; }
.saved-state { color: #67c23a; font-size: 13px; }
.editor-grid { display: grid; grid-template-columns: 250px minmax(440px, 1fr) 390px; gap: 14px; align-items: start; }
.editor-panel { min-width: 0; padding: 18px; border: 1px solid #e5e7eb; border-radius: 10px; background: #fff; }
.left-panel, .right-panel { position: sticky; top: 16px; max-height: calc(100vh - 120px); overflow-y: auto; }
.left-panel { display: grid; gap: 24px; }
.questionnaire-form { padding-bottom: 8px; border-bottom: 1px solid #e5e7eb; }
.page-heading { margin-bottom: 14px; color: #64748b; font-size: 13px; }
.canvas-summary { margin: 16px 0; color: #64748b; font-size: 13px; }
.question-card { margin-top: 14px; padding: 20px; border: 1px solid #dcdfe6; border-radius: 9px; cursor: pointer; transition: 0.2s ease; }
.question-card.active { border-color: #409eff; box-shadow: 0 0 0 2px rgb(64 158 255 / 12%); }
.question-index { margin-bottom: 12px; color: #909399; font-size: 12px; }
.validation-issues { margin-top: 16px; padding: 12px; border-radius: 8px; color: #b45309; background: #fff7ed; font-size: 13px; }
.validation-issues ul { margin: 8px 0 0; padding-left: 20px; }
@media (max-width: 1380px) {
  .editor-grid { grid-template-columns: 220px minmax(420px, 1fr); }
  .right-panel { position: static; grid-column: 1 / -1; max-height: none; }
}
@media (max-width: 860px) {
  .editor-header, .editor-actions { align-items: flex-start; flex-wrap: wrap; }
  .editor-grid { grid-template-columns: 1fr; }
  .left-panel, .right-panel { position: static; max-height: none; }
}
</style>
