<script setup>
import FilePlusIcon from '@iconify-vue/lucide/file-plus'
import FileTextIcon from '@iconify-vue/lucide/file-text'
import ArrowUpIcon from '@iconify-vue/lucide/arrow-up'
import ArrowDownIcon from '@iconify-vue/lucide/arrow-down'
import TrashIcon from '@iconify-vue/lucide/trash-2'
import { computed } from 'vue'
import { getQuestionTypeDefinition } from './questions/questionTypeRegistry'

const props = defineProps({
  draft: { type: Object, required: true },
  selectedPageCode: { type: String, default: '' },
  selectedQuestionCode: { type: String, default: '' },
  disabled: { type: Boolean, default: false }
})
defineEmits(['select-page', 'select-question', 'add-page', 'move-page', 'delete-page'])
const questionNumbers = computed(() => new Map(props.draft.pages.flatMap(page => page.questions)
  .map((question, index) => [question.questionCode, index + 1])))
</script>

<template>
  <section class="questionnaire-outline">
    <div v-if="draft.pages.length > 0 && draft.pages.every(page => page.questions.length > 0)" class="panel-title">
      <el-tooltip content="增加页面" :trigger="['hover', 'focus']" :trigger-keys="[]" :enterable="false">
        <el-button class="add-page" text size="small" type="primary" aria-label="增加页面" :disabled="disabled || draft.pages.length >= 50" @click="$emit('add-page')">
          <FilePlusIcon width="14" height="14" aria-hidden="true" />
        </el-button>
      </el-tooltip>
    </div>
    <div class="outline-pages" aria-label="问卷页面与题目" tabindex="0">
    <div
      v-for="(page, pageIndex) in draft.pages"
      :key="page.pageCode"
      :class="['outline-page-group', { active: page.pageCode === selectedPageCode }]"
    >
      <div class="outline-page">
        <el-button text size="small" :disabled="disabled" class="page-select" :aria-label="`${pageIndex + 1}. ${page.pageTitle}`" :aria-current="page.pageCode === selectedPageCode ? 'page' : undefined" :title="page.pageTitle" @click="$emit('select-page', page.pageCode)">
          <FileTextIcon width="14" height="14" aria-hidden="true" /><span class="page-name">{{ page.pageTitle }}</span>
        </el-button>
      <div class="page-actions">
        <el-tooltip content="上移页面" :trigger="['hover', 'focus']" :trigger-keys="[]" :enterable="false">
          <el-button link size="small" :disabled="disabled || pageIndex === 0" :aria-label="`上移页面：${page.pageTitle}`" @click="$emit('move-page', page.pageCode, -1)"><ArrowUpIcon width="10" height="10" aria-hidden="true" /></el-button>
        </el-tooltip>
        <el-tooltip content="下移页面" :trigger="['hover', 'focus']" :trigger-keys="[]" :enterable="false">
          <el-button link size="small" :disabled="disabled || pageIndex === draft.pages.length - 1" :aria-label="`下移页面：${page.pageTitle}`" @click="$emit('move-page', page.pageCode, 1)"><ArrowDownIcon width="10" height="10" aria-hidden="true" /></el-button>
        </el-tooltip>
        <el-tooltip content="删除页面" :trigger="['hover', 'focus']" :trigger-keys="[]" :enterable="false">
          <el-button link size="small" type="danger" :disabled="disabled || draft.pages.length <= 1" :aria-label="`删除页面：${page.pageTitle}`" @click="$emit('delete-page', page.pageCode)"><TrashIcon width="10" height="10" aria-hidden="true" /></el-button>
        </el-tooltip>
      </div>
        <small>{{ page.questions.length }} 题</small>
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
      <p v-if="!page.questions.length" class="outline-empty">当前页面暂无题目</p>
    </div>
    </div>


  </section>
</template>

<style scoped>
.questionnaire-outline { display: flex; flex-direction: column; min-height: 0; }
.outline-pages { flex: 1; min-height: 0; overflow-y: auto; overscroll-behavior: contain; }
.outline-pages:focus-visible { outline: 2px solid #409eff; outline-offset: -2px; border-radius: 4px; }
.panel-title, .outline-page { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.panel-title { flex: 0 0 26px; box-sizing: border-box; justify-content: flex-end; margin-bottom: 0; padding: 0 6px; border-bottom: 1px solid var(--fb-border, #e5e7eb); background: #f3f5f8; }
.add-page { width: 24px; height: 24px; padding: 0; }
.outline-page-group { min-width: 0; margin-bottom: 10px; padding: 6px 0; }
.outline-page-group + .outline-page-group { border-top: 1px solid var(--fb-border, #e5e7eb); box-shadow: 0 -4px 6px -4px rgb(15 23 42 / 12%); }
.outline-page { padding: 0 8px 4px; gap: 3px; margin-bottom: 4px; border-bottom: 1px solid var(--fb-border, #f0f2f5); }
.page-select { flex: 1; min-width: 0; padding: 4px 0; justify-content: flex-start; font-weight: 600; }
.page-select:deep(> span) { display: flex; gap: 6px; min-width: 0; }
.page-select svg { flex: none; color: #409eff; }
.page-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.outline-page small { flex: none; padding: 2px 5px; border-radius: 4px; color: var(--fb-text-muted, #909399); background: var(--fb-surface-muted, #f4f4f5); font-size: 11px; }
.page-actions { display: flex; flex: none; align-items: center; gap: 0; }
.page-actions .el-button { width: 18px; height: 22px; padding: 0; margin-left: 0; }
.page-actions { justify-content: flex-end; }
.page-actions { opacity: .45; transition: opacity .15s; }
.outline-page-group:hover .page-actions, .outline-page-group:focus-within .page-actions { opacity: 1; }
@media (hover: none) { .page-actions { opacity: 1; } }
.outline-question { display: flex; width: 100%; min-height: 28px; margin: 2px 0 0; justify-content: flex-start; padding: 5px 6px; color: var(--fb-text-regular, #606266); border-radius: 5px; }
.outline-question:deep(> span) { display: flex; align-items: center; gap: 6px; width: 100%; min-width: 0; }
.outline-question svg { flex: none; color: var(--fb-text-muted, #909399); }
.question-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; line-height: 18px; }
.outline-question:hover, .outline-question:focus-visible { background: var(--fb-surface-muted, #f5f7fa); }
.outline-question.active { color: var(--el-color-primary); font-weight: 600; background: var(--fb-primary-bg, #ecf5ff); }
.outline-question.active svg { color: #409eff; }
.outline-empty { margin: 10px; text-align: center; font-size: 12px; color: var(--fb-text-disabled, #a8abb2); }
</style>
