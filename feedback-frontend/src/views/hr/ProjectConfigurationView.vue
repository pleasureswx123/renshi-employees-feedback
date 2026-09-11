<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import QuestionnaireEditorView from './QuestionnaireEditorView.vue'
import PublicationConfigView from './PublicationConfigView.vue'
import { useQuestionnaireDraftStore } from '@/stores/questionnaireDraft'
import { usePublicationConfigStore } from '@/stores/publicationConfig'
import { usePermissionStore } from '@/stores/permission'

const route = useRoute()
const router = useRouter()
const permission = usePermissionStore()
const draftStore = useQuestionnaireDraftStore()
const publicationStore = usePublicationConfigStore()
const child = ref(null)
const parseStep = value => Math.min(5, Math.max(0, (Number(value) || 1) - 1))
const canEdit = permission.hasPermission('feedback:questionnaire:edit')
const step = ref(canEdit ? parseStep(route.query.step) : Math.max(2, parseStep(route.query.step)))
const projectName = computed(() => draftStore.draft?.projectName || publicationStore.config?.projectName || '评价项目')
function changeStep(value) {
  step.value = value
  if (route.query.step !== String(value + 1)) router.replace({ query: { ...route.query, step: String(value + 1) } })
}
// 浏览器前进、后退或手动修改步骤仍经过子步骤的校验及保存流程。
watch(() => route.query.step, async value => {
  const requested = parseStep(value)
  if (requested === step.value) return
  await child.value?.goPreparationStep(requested)
  if (parseStep(route.query.step) !== step.value) changeStep(step.value)
})
</script>

<template>
  <section class="configuration-workspace">
    <header class="configuration-heading workspace-page-header">
      <el-button text @click="router.push('/hr/projects')">返回项目列表</el-button>
      <h1>项目配置</h1><span>{{ projectName }}</span>
    </header>
    <QuestionnaireEditorView v-if="step < 2 && canEdit" ref="child" embedded :initial-step="step" @step-change="changeStep" />
    <PublicationConfigView v-else ref="child" embedded :initial-step="step" @step-change="changeStep" />
  </section>
</template>

<style scoped>
.configuration-workspace { height: calc(100dvh - 110px); min-height: 600px; display: grid; grid-template-rows: auto minmax(0, 1fr); gap: 16px; }
.configuration-heading { display: flex; align-items: center; gap: 16px; padding: 10px 14px; min-width: 0; }
.configuration-heading h1 { margin: 0; font-size: 18px; white-space: nowrap; }
.configuration-heading span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--fb-text-muted); }
</style>
