<script setup>
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'

import QuestionnairePreviewDialog from '@/components/feedback/QuestionnairePreviewDialog.vue'
import QuestionRenderer from '@/components/feedback/questions/QuestionRenderer.vue'
import SingleChoiceProperties from '@/components/feedback/questions/SingleChoiceProperties.vue'
import { useQuestionnaireDraftStore } from '@/stores/questionnaireDraft'
import { calculateRawMaxScore } from '@/utils/questionnaireDraft'

const route = useRoute()
const router = useRouter()
const draftStore = useQuestionnaireDraftStore()
const questionnaireFormRef = ref()
const propertiesRef = ref()
const previewVisible = ref(false)
const projectId = Number(route.params.projectId)
const draft = computed(() => draftStore.draft)
const selectedQuestion = computed(() => draftStore.selectedQuestion)
const selectedQuestionIndex = computed(() =>
  draft.value?.pages[0]?.questions.findIndex(
    question => question.questionCode === draftStore.selectedQuestionCode
  ) ?? -1
)
const canMoveSelectedQuestionUp = computed(() => selectedQuestionIndex.value > 0)
const canMoveSelectedQuestionDown = computed(() => {
  const questionCount = draft.value?.pages[0]?.questions.length || 0
  return selectedQuestionIndex.value >= 0 && selectedQuestionIndex.value < questionCount - 1
})
const rawMaxScore = computed(() => calculateRawMaxScore(draft.value))
const questionnaireRules = {
  title: [{ required: true, message: '请填写问卷标题', trigger: 'blur' }],
  'pages.0.pageTitle': [{ required: true, message: '请填写页面标题', trigger: 'blur' }]
}

function changeDraftField(field, value) {
  draft.value[field] = value
  draftStore.markDirty()
}

function changePageField(field, value) {
  draft.value.pages[0][field] = value
  draftStore.markDirty()
}

function updateSelectedQuestion(question) {
  draftStore.updateQuestion(question)
}

async function removeSelectedQuestion() {
  await ElMessageBox.confirm('确认删除当前单选题吗？该操作会在下次保存草稿时持久化。', '删除题目', {
    type: 'warning',
    confirmButtonText: '删除题目',
    cancelButtonText: '取消'
  })
  draftStore.removeSelectedQuestion()
}

async function saveDraft() {
  if (draftStore.saving) return
  try {
    await questionnaireFormRef.value?.validate()
    await propertiesRef.value?.validate()
    const errors = draftStore.validate()
    if (errors.length) {
      ElMessage.warning(errors[0])
      return
    }
    await draftStore.save()
    ElMessage.success('问卷草稿已保存到 PostgreSQL')
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
          <h1>问卷编辑器</h1>
        </div>
      </div>
      <div class="editor-actions">
        <span v-if="draftStore.dirty" class="dirty-state">有未保存修改</span>
        <span v-else-if="draftStore.lastSavedAt" class="saved-state">草稿已保存</span>
        <el-button :disabled="!draft" @click="openPreview">电脑 / 手机预览</el-button>
        <el-button type="primary" :loading="draftStore.saving" :disabled="!draft" @click="saveDraft">
          保存草稿
        </el-button>
      </div>
    </header>

    <el-alert
      title="P3仅开放单选题草稿；页面、指标和其他题型将在后续阶段基于同一协议扩展。"
      type="info"
      :closable="false"
      show-icon
    />

    <div v-if="draft" class="editor-grid">
      <aside class="left-panel editor-panel">
        <section>
          <div class="panel-title">
            <strong>问卷大纲</strong>
            <el-tag size="small">1页</el-tag>
          </div>
          <div class="outline-page">
            <span>{{ draft.pages[0].pageTitle }}</span>
            <small>{{ draft.pages[0].questions.length }}题</small>
          </div>
          <button
            v-for="(question, index) in draft.pages[0].questions"
            :key="question.questionCode"
            type="button"
            :class="['outline-question', { active: question.questionCode === draftStore.selectedQuestionCode }]"
            @click="draftStore.selectQuestion(question.questionCode)"
          >
            <span>{{ index + 1 }}. {{ question.title }}</span>
          </button>
        </section>
        <section class="type-panel">
          <div class="panel-title"><strong>题型面板</strong></div>
          <el-button class="question-type-button" plain @click="draftStore.addSingleChoice">
            <span>单选题</span>
            <small>选项、分值、附加原因</small>
          </el-button>
        </section>
      </aside>

      <main class="canvas-panel editor-panel">
        <el-form
          ref="questionnaireFormRef"
          :model="draft"
          :rules="questionnaireRules"
          label-position="top"
          class="questionnaire-form"
        >
          <el-form-item label="问卷标题" prop="title">
            <el-input
              :model-value="draft.title"
              maxlength="200"
              show-word-limit
              @input="changeDraftField('title', $event)"
            />
          </el-form-item>
          <el-form-item label="问卷说明">
            <el-input
              :model-value="draft.description"
              type="textarea"
              :rows="3"
              maxlength="5000"
              placeholder="向参评员工说明评价目的和填写口径"
              @input="changeDraftField('description', $event)"
            />
          </el-form-item>
          <el-form-item label="页面标题" prop="pages.0.pageTitle">
            <el-input
              :model-value="draft.pages[0].pageTitle"
              maxlength="200"
              @input="changePageField('pageTitle', $event)"
            />
          </el-form-item>
        </el-form>

        <div class="canvas-summary">
          <span>题目画布</span>
          <span>原始满分预览：{{ rawMaxScore.toFixed(4) }}</span>
        </div>
        <el-empty
          v-if="!draft.pages[0].questions.length"
          description="从左侧题型面板添加第一道单选题"
          :image-size="92"
        />
        <article
          v-for="(question, index) in draft.pages[0].questions"
          :key="question.questionCode"
          :class="['question-card', { active: question.questionCode === draftStore.selectedQuestionCode }]"
          @click="draftStore.selectQuestion(question.questionCode)"
        >
          <div class="question-index">第 {{ index + 1 }} 题 · 单选题</div>
          <QuestionRenderer :question="question" mode="editor" />
        </article>
      </main>

      <aside class="right-panel editor-panel">
        <SingleChoiceProperties
          v-if="selectedQuestion"
          ref="propertiesRef"
          :question="selectedQuestion"
          :can-move-up="canMoveSelectedQuestionUp"
          :can-move-down="canMoveSelectedQuestionDown"
          @change="updateSelectedQuestion"
          @duplicate="draftStore.duplicateSelectedQuestion"
          @move-up="draftStore.moveSelectedQuestion(-1)"
          @move-down="draftStore.moveSelectedQuestion(1)"
          @delete="removeSelectedQuestion"
        />
        <el-empty v-else description="选择一道题后配置属性" :image-size="84" />
      </aside>
    </div>

    <QuestionnairePreviewDialog v-model="previewVisible" :draft="draft" />
  </section>
</template>

<style scoped>
.editor-page {
  display: grid;
  gap: 16px;
  min-height: calc(100vh - 120px);
}

.editor-header,
.editor-heading,
.editor-actions,
.panel-title,
.canvas-summary,
.outline-page {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.editor-heading {
  justify-content: flex-start;
}

.editor-heading p,
.editor-heading h1 {
  margin: 0;
}

.editor-heading p {
  margin-bottom: 3px;
  color: #64748b;
  font-size: 13px;
}

.editor-heading h1 {
  color: #111827;
  font-size: 22px;
}

.dirty-state {
  color: #e6a23c;
  font-size: 13px;
}

.saved-state {
  color: #67c23a;
  font-size: 13px;
}

.editor-grid {
  display: grid;
  grid-template-columns: 230px minmax(440px, 1fr) 360px;
  gap: 14px;
  align-items: start;
}

.editor-panel {
  min-width: 0;
  padding: 18px;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  background: #fff;
}

.left-panel,
.right-panel {
  position: sticky;
  top: 16px;
  max-height: calc(100vh - 120px);
  overflow-y: auto;
}

.left-panel {
  display: grid;
  gap: 24px;
}

.panel-title {
  margin-bottom: 12px;
}

.outline-page {
  padding: 10px;
  border-radius: 7px;
  background: #f3f6fa;
}

.outline-page small {
  color: #909399;
}

.outline-question {
  display: block;
  overflow: hidden;
  width: 100%;
  margin-top: 6px;
  padding: 9px 10px;
  border: 0;
  border-radius: 6px;
  color: #475569;
  background: transparent;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
}

.outline-question.active,
.outline-question:hover {
  color: #409eff;
  background: #ecf5ff;
}

.question-type-button {
  width: 100%;
  height: auto;
  padding: 14px;
}

.question-type-button :deep(span) {
  display: grid;
  gap: 3px;
  justify-items: start;
}

.question-type-button small {
  color: #909399;
}

.questionnaire-form {
  padding-bottom: 8px;
  border-bottom: 1px solid #e5e7eb;
}

.canvas-summary {
  margin: 16px 0;
  color: #64748b;
  font-size: 13px;
}

.question-card {
  margin-top: 14px;
  padding: 20px;
  border: 1px solid #dcdfe6;
  border-radius: 9px;
  cursor: pointer;
  transition: 0.2s ease;
}

.question-card.active {
  border-color: #409eff;
  box-shadow: 0 0 0 2px rgb(64 158 255 / 12%);
}

.question-index {
  margin-bottom: 12px;
  color: #909399;
  font-size: 12px;
}

@media (max-width: 1280px) {
  .editor-grid {
    grid-template-columns: 210px minmax(420px, 1fr);
  }

  .right-panel {
    position: static;
    grid-column: 1 / -1;
    max-height: none;
  }
}

@media (max-width: 860px) {
  .editor-header,
  .editor-actions {
    align-items: flex-start;
    flex-wrap: wrap;
  }

  .editor-grid {
    grid-template-columns: 1fr;
  }

  .left-panel,
  .right-panel {
    position: static;
    max-height: none;
  }
}
</style>
