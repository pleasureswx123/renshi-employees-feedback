<script setup>
import { reactive, ref, watch } from 'vue'

import QuestionRenderer from './questions/QuestionRenderer.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  draft: { type: Object, default: null }
})

const emit = defineEmits(['update:modelValue'])
const previewMode = ref('desktop')
const answers = reactive({})

watch(
  () => props.modelValue,
  visible => {
    if (!visible) return
    for (const key of Object.keys(answers)) delete answers[key]
  }
)

function close() {
  emit('update:modelValue', false)
}

function updateAnswer(questionCode, value) {
  answers[questionCode] = value
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="问卷预览"
    width="min(960px, 94vw)"
    destroy-on-close
    @close="close"
  >
    <div class="preview-toolbar">
      <el-radio-group v-model="previewMode" aria-label="预览设备">
        <el-radio-button value="desktop">电脑</el-radio-button>
        <el-radio-button value="mobile">手机</el-radio-button>
      </el-radio-group>
      <span>预览内容不会保存为正式答案</span>
    </div>
    <div :class="['preview-stage', `is-${previewMode}`]">
      <article v-if="draft" class="preview-document">
        <header>
          <h2>{{ draft.title }}</h2>
          <p v-if="draft.description">{{ draft.description }}</p>
        </header>
        <section v-for="page in draft.pages" :key="page.pageId || page.sortOrder" class="preview-page">
          <h3>{{ page.pageTitle }}</h3>
          <p v-if="page.pageDescription">{{ page.pageDescription }}</p>
          <el-empty v-if="!page.questions.length" description="当前页面还没有题目" :image-size="72" />
          <div v-for="question in page.questions" :key="question.questionCode" class="preview-question">
            <QuestionRenderer
              :question="question"
              mode="preview"
              :model-value="answers[question.questionCode]"
              @update:model-value="updateAnswer(question.questionCode, $event)"
            />
          </div>
        </section>
      </article>
    </div>
    <template #footer>
      <el-button type="primary" @click="close">关闭预览</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.preview-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
  color: #64748b;
  font-size: 13px;
}

.preview-stage {
  overflow-x: hidden;
  min-height: 520px;
  padding: 28px;
  border-radius: 10px;
  background: #eef2f7;
}

.preview-document {
  width: min(760px, 100%);
  margin: 0 auto;
  padding: 32px;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 8px 30px rgb(15 23 42 / 8%);
}

.preview-document h2,
.preview-page h3 {
  margin-top: 0;
}

.preview-document header p,
.preview-page > p {
  color: #64748b;
  line-height: 1.7;
}

.preview-question {
  margin-top: 18px;
  padding: 20px;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
}

.preview-stage.is-mobile .preview-document {
  width: 375px;
  max-width: 100%;
  padding: 20px 16px;
}

.preview-stage.is-mobile {
  padding-inline: 12px;
}

@media (max-width: 600px) {
  .preview-toolbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .preview-stage {
    padding: 10px;
  }
}
</style>
