<script setup>
defineProps({
  draft: { type: Object, required: true },
  selectedPageCode: { type: String, default: '' },
  selectedQuestionCode: { type: String, default: '' }
})
defineEmits(['select-page', 'select-question', 'add-page', 'move-page', 'delete-page'])
</script>

<template>
  <section>
    <div class="panel-title">
      <strong>问卷大纲</strong>
      <el-button link type="primary" :disabled="draft.pages.length >= 50" @click="$emit('add-page')">
        增加页面
      </el-button>
    </div>
    <div
      v-for="(page, pageIndex) in draft.pages"
      :key="page.pageCode"
      :class="['outline-page-group', { active: page.pageCode === selectedPageCode }]"
    >
      <div class="outline-page" @click="$emit('select-page', page.pageCode)">
        <span>{{ pageIndex + 1 }}. {{ page.pageTitle }}</span>
        <small>{{ page.questions.length }}题</small>
      </div>
      <div class="page-actions">
        <el-button link size="small" :disabled="pageIndex === 0" @click="$emit('move-page', page.pageCode, -1)">上移</el-button>
        <el-button link size="small" :disabled="pageIndex === draft.pages.length - 1" @click="$emit('move-page', page.pageCode, 1)">下移</el-button>
        <el-button link size="small" type="danger" :disabled="draft.pages.length <= 1" @click="$emit('delete-page', page.pageCode)">删除</el-button>
      </div>
      <el-button
        v-for="(question, questionIndex) in page.questions"
        :key="question.questionCode"
        link
        :class="['outline-question', { active: question.questionCode === selectedQuestionCode }]"
        @click="$emit('select-question', question.questionCode)"
      >{{ questionIndex + 1 }}. {{ question.title }}</el-button>
    </div>
  </section>
</template>

<style scoped>
.panel-title, .outline-page { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.panel-title { margin-bottom: 12px; }
.outline-page-group { margin-bottom: 10px; padding: 6px; border: 1px solid transparent; border-radius: 8px; }
.outline-page-group.active { border-color: #b3d8ff; background: #f5faff; }
.outline-page { padding: 8px; border-radius: 6px; background: #f3f6fa; cursor: pointer; }
.outline-page small { flex: none; color: #909399; }
.page-actions { display: flex; justify-content: flex-end; }
.page-actions :deep(.el-button + .el-button) { margin-left: 4px; }
.outline-question { display: block; overflow: hidden; width: 100%; justify-content: flex-start; padding: 6px 8px; color: #475569; text-overflow: ellipsis; white-space: nowrap; }
.outline-question.active { color: #409eff; background: #ecf5ff; }
</style>
