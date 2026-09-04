<script setup>
import PencilIcon from '@iconify-vue/lucide/pencil'
import FileTextIcon from '@iconify-vue/lucide/file-text'
import ArrowUpIcon from '@iconify-vue/lucide/arrow-up'
import ArrowDownIcon from '@iconify-vue/lucide/arrow-down'
import TrashIcon from '@iconify-vue/lucide/trash-2'
import { computed, nextTick, reactive, ref } from 'vue'
import { getQuestionTypeDefinition } from './questions/questionTypeRegistry'

const props = defineProps({
  draft: { type: Object, required: true },
  selectedPageCode: { type: String, default: '' },
  selectedQuestionCode: { type: String, default: '' },
  disabled: { type: Boolean, default: false }
})
const emit = defineEmits(['select-page', 'select-question', 'add-page', 'move-page', 'delete-page', 'update-page'])
const questionNumbers = computed(() => new Map(props.draft.pages.flatMap(page => page.questions)
  .map((question, index) => [question.questionCode, index + 1])))
const renameVisible = ref(false)
const renamePending = ref(false)
const renameFormRef = ref()
const renameInputRef = ref()
const renameForm = reactive({ pageCode: '', pageTitle: '' })

function openRename(page) {
  if (props.disabled) return
  Object.assign(renameForm, { pageCode: page.pageCode, pageTitle: page.pageTitle })
  renameVisible.value = true
}

async function focusRename() {
  await nextTick()
  renameFormRef.value?.clearValidate()
  renameInputRef.value?.focus()
  renameInputRef.value?.select()
}

async function renamePage() {
  if (props.disabled || renamePending.value) return
  renamePending.value = true
  try {
    await renameFormRef.value.validate()
    if (!renameVisible.value || !props.draft.pages.some(page => page.pageCode === renameForm.pageCode)) return
    emit('update-page', renameForm.pageCode, { pageTitle: renameForm.pageTitle.trim() })
    renameVisible.value = false
  } catch {
    // 保留输入并显示 Element Plus 字段校验提示。
  } finally {
    renamePending.value = false
  }
}
</script>

<template>
  <section class="questionnaire-outline">
    <div class="panel-title">
      <strong>问卷大纲</strong>
      <el-button link size="small" type="primary" :disabled="disabled || draft.pages.length >= 50" @click="$emit('add-page')">
        增加页面
      </el-button>
    </div>
    <div class="outline-pages" aria-label="问卷页面与题目" tabindex="0">
    <div
      v-for="(page, pageIndex) in draft.pages"
      :key="page.pageCode"
      :class="['outline-page-group', { active: page.pageCode === selectedPageCode }]"
    >
      <div class="outline-page">
        <el-button text size="small" :disabled="disabled" class="page-select" :aria-label="`${pageIndex + 1}. ${page.pageTitle}`" :aria-current="page.pageCode === selectedPageCode ? 'page' : undefined" :title="page.pageTitle" @click="$emit('select-page', page.pageCode)">
          <FileTextIcon width="16" height="16" aria-hidden="true" /><span class="page-name">{{ page.pageTitle }}</span>
        </el-button>
        <small>{{ page.questions.length }} 题</small>
      </div>
      <div class="page-actions">
        <el-tooltip content="重命名页面" :trigger="['hover', 'focus']" :trigger-keys="[]" :enterable="false">
          <el-button link size="small" class="rename-page" :disabled="disabled" :aria-label="`重命名页面：${page.pageTitle}`" @click="openRename(page)"><PencilIcon width="14" height="14" aria-hidden="true" /></el-button>
        </el-tooltip>
        <el-tooltip content="上移页面" :trigger="['hover', 'focus']" :trigger-keys="[]" :enterable="false">
          <el-button link size="small" :disabled="disabled || pageIndex === 0" :aria-label="`上移页面：${page.pageTitle}`" @click="$emit('move-page', page.pageCode, -1)"><ArrowUpIcon width="14" height="14" aria-hidden="true" /></el-button>
        </el-tooltip>
        <el-tooltip content="下移页面" :trigger="['hover', 'focus']" :trigger-keys="[]" :enterable="false">
          <el-button link size="small" :disabled="disabled || pageIndex === draft.pages.length - 1" :aria-label="`下移页面：${page.pageTitle}`" @click="$emit('move-page', page.pageCode, 1)"><ArrowDownIcon width="14" height="14" aria-hidden="true" /></el-button>
        </el-tooltip>
        <el-tooltip content="删除页面" :trigger="['hover', 'focus']" :trigger-keys="[]" :enterable="false">
          <el-button link size="small" type="danger" :disabled="disabled || draft.pages.length <= 1" :aria-label="`删除页面：${page.pageTitle}`" @click="$emit('delete-page', page.pageCode)"><TrashIcon width="14" height="14" aria-hidden="true" /></el-button>
        </el-tooltip>
      </div>
      <el-button
        v-for="question in page.questions"
        :key="question.questionCode"
        link
        size="small"
        :class="['outline-question', { active: question.questionCode === selectedQuestionCode }]"
        :disabled="disabled"
        :aria-current="question.questionCode === selectedQuestionCode ? 'true' : undefined"
        :title="question.title.trim() || `${getQuestionTypeDefinition(question.questionType)?.label} · 待填写`"
        @click="$emit('select-question', question.questionCode)"
      ><component :is="getQuestionTypeDefinition(question.questionType)?.icon" width="15" height="15" aria-hidden="true" /><span class="question-name">{{ questionNumbers.get(question.questionCode) }}. {{ question.title.trim() || `${getQuestionTypeDefinition(question.questionType)?.label} · 待填写` }}</span></el-button>
      <p v-if="!page.questions.length" class="outline-empty">从下方添加题目</p>
    </div>
    </div>

    <el-dialog v-model="renameVisible" title="重命名页面" width="min(420px, 94vw)" append-to-body @opened="focusRename">
      <el-form ref="renameFormRef" :model="renameForm" :disabled="disabled || renamePending" label-position="top">
        <el-form-item label="页面标题" prop="pageTitle" :rules="[{ required: true, whitespace: true, message: '请填写页面标题', trigger: 'blur' }]">
          <el-input ref="renameInputRef" v-model="renameForm.pageTitle" maxlength="200" show-word-limit @keydown.enter.prevent="renamePage" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button size="small" @click="renameVisible = false">取消</el-button>
        <el-button size="small" type="primary" :loading="renamePending" :disabled="disabled" @click="renamePage">确定</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.questionnaire-outline { display: flex; flex-direction: column; min-height: 0; }
.outline-pages { flex: 1; min-height: 0; overflow-y: auto; overscroll-behavior: contain; scrollbar-gutter: stable; }
.outline-pages:focus-visible { outline: 2px solid #409eff; outline-offset: -2px; border-radius: 4px; }
.panel-title, .outline-page { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.panel-title { flex: none; margin-bottom: 10px; font-size: 13px; }
.outline-page-group { min-width: 0; margin-bottom: 10px; padding: 6px; border: 1px solid var(--fb-border, #ebeef5); border-radius: 8px; }
.outline-page-group.active { border-color: var(--fb-primary-border, #c6e2ff); }
.outline-page { padding: 0 4px; gap: 4px; }
.page-select { flex: 1; min-width: 0; padding: 4px 0; justify-content: flex-start; font-weight: 600; }
.page-select:deep(> span) { display: flex; gap: 6px; min-width: 0; }
.page-select svg { flex: none; color: #409eff; }
.page-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.outline-page small { flex: none; padding: 2px 5px; border-radius: 4px; color: var(--fb-text-muted, #909399); background: var(--fb-surface-muted, #f4f4f5); font-size: 11px; }
.page-actions { display: flex; align-items: center; gap: 2px; margin-bottom: 4px; padding-bottom: 4px; border-bottom: 1px solid var(--fb-border, #f0f2f5); }
.page-actions .el-button { width: 24px; height: 26px; padding: 0; margin-left: 0; }
.page-actions .rename-page { margin-right: auto; }
.outline-question { display: flex; width: 100%; min-height: 28px; margin: 2px 0 0; justify-content: flex-start; padding: 5px 6px; color: var(--fb-text-regular, #606266); border-radius: 5px; }
.outline-question:deep(> span) { display: flex; align-items: center; gap: 6px; width: 100%; min-width: 0; }
.outline-question svg { flex: none; color: var(--fb-text-muted, #909399); }
.question-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; line-height: 18px; }
.outline-question:hover, .outline-question:focus-visible { background: var(--fb-surface-muted, #f5f7fa); }
.outline-question.active { color: #409eff; background: var(--fb-primary-bg, #ecf5ff); box-shadow: inset 3px 0 #409eff; }
.outline-question.active svg { color: #409eff; }
.outline-empty { margin: 10px 4px; font-size: 12px; color: var(--fb-text-disabled, #a8abb2); }
</style>
