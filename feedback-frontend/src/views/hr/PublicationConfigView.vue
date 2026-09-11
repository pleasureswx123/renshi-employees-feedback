<script setup>
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { getParticipantDepartments, listParticipantOptions } from '@/api/feedback/projects'

import EvaluatorSelectionPanel from '@/components/feedback/publication/EvaluatorSelectionPanel.vue'
import ProjectPreparationSteps from '@/components/feedback/ProjectPreparationSteps.vue'
import PublicationConfigurationReview from '@/components/feedback/publication/PublicationConfigurationReview.vue'
import PublicationPreviewPanel from '@/components/feedback/publication/PublicationPreviewPanel.vue'
import PublicationDetails from '@/components/feedback/publication/PublicationDetails.vue'
import RelationConfigPanel from '@/components/feedback/publication/RelationConfigPanel.vue'
import TargetSelectorPanel from '@/components/feedback/publication/TargetSelectorPanel.vue'
import { usePermissionStore } from '@/stores/permission'
import { usePublicationConfigStore } from '@/stores/publicationConfig'
import { SELF_RELATION_CODE } from '@/utils/publicationConfig'
import { analyzePublicationWorkflow, PUBLICATION_STEPS, publicationIssueDestination } from '@/utils/publicationWorkflow'

const props = defineProps({ embedded: Boolean, initialStep: { type: Number, default: 2 } })
const emit = defineEmits(['step-change'])
const route = useRoute()
const router = useRouter()
const permissionStore = usePermissionStore()
const publicationStore = usePublicationConfigStore()
const projectId = Number(route.params.projectId)
const config = computed(() => publicationStore.config)
const activeStep = ref(0)
const evaluationMode = ref('')
const evaluationModeForm = ref(null)
const modeChanging = ref(false)
const evaluatorPanel = ref(null)
const stepContent = ref(null)
const busy = computed(() => publicationStore.saving || publicationStore.publishing || modeChanging.value)
const workflow = computed(() => analyzePublicationWorkflow(config.value, evaluationMode.value))
const currentIssues = computed(() => [workflow.value.targetIssues, workflow.value.relationIssues, workflow.value.assignmentIssues.map(item => item.message)][activeStep.value] || [])
const nextLabel = computed(() => activeStep.value === 1 && evaluationMode.value === 'self' ? '保存并检查发布条件' : activeStep.value === 2 ? '保存并检查发布条件' : `下一步：${PUBLICATION_STEPS[activeStep.value + 1]}`)
const stepDescriptions = computed(() => [
  config.value?.targets.length ? `已选 ${config.value.targets.length} 人` : '选择本轮被评价员工',
  !evaluationMode.value ? '请选择评价方式' : evaluationMode.value === 'self' ? '仅自评' : `计分关系权重 ${workflow.value.totalWeight}%`,
  evaluationMode.value === 'self' ? '自动添加自评，无需分配' : workflow.value.assignmentIssues.length ? `待处理 ${workflow.value.assignmentIssues.length} 项` : '核对每人的评价安排',
  publicationStore.dirty ? '修改后需重新检查' : config.value?.isPublishReady ? '检查已通过' : '保存后检查发布条件'
])
const canManage = computed(() => permissionStore.hasPermission('feedback:participant:manage'))
const canEditQuestionnaire = computed(() => permissionStore.hasPermission('feedback:questionnaire:edit'))
const questionnaireNeedsCheck = computed(() => config.value?.validationIssues.some(issue => publicationIssueDestination(issue) === 'editor'))
const completedSteps = computed(() => [
  ...(!questionnaireNeedsCheck.value ? [0, 1] : []),
  ...(!workflow.value.targetIssues.length ? [2] : []),
  ...(!workflow.value.relationIssues.length ? [3] : []),
  ...(!workflow.value.targetIssues.length && !workflow.value.relationIssues.length && !workflow.value.assignmentIssues.length ? [4] : [])
])
const preparationDescriptions = computed(() => [
  questionnaireNeedsCheck.value ? '问卷或指标需检查' : '已配置，可返回修改',
  questionnaireNeedsCheck.value ? '问卷或指标需检查' : '已配置，可返回修改',
  ...stepDescriptions.value
])
const participantDirectory = computed(() => Array.from(publicationStore.participantDirectory.values()))

async function loadTargetDepartments() {
  if (!canManage.value || !config.value?.editable) return []
  return (await getParticipantDepartments(projectId)).data || []
}

async function loadTargetPeople(params) {
  if (!canManage.value || !config.value?.editable) return { rows: [], total: 0 }
  const currentConfig = config.value
  const response = await listParticipantOptions(projectId, params)
  // 组织树不再经过旧分页列表，须同步缓存人员资料，避免已选名单只有编号。
  if (config.value === currentConfig && currentConfig.editable) {
    for (const person of response.rows || []) publicationStore.rememberParticipant(person)
  }
  return response
}

async function saveConfig() {
  if (busy.value || !canManage.value) return null
  try {
    const saved = await publicationStore.save()
    if (!saved) return
    if (saved.validationIssues.length) {
      ElMessage.success(`配置已保存；仍有${saved.validationIssues.length}项发布前检查待处理`)
    } else {
      ElMessage.success('配置已保存，发布前检查已通过')
    }
    return saved
  } catch (error) {
    if (!error.status) ElMessage.warning(error.message)
  }
}

function showStep(step) {
  activeStep.value = step
  emit('step-change', step + 2)
  nextTick(() => stepContent.value?.scrollIntoView?.({ block: 'start' }))
}

async function goStep(step) {
  if (busy.value) return
  if (step === 2 && evaluationMode.value === 'self') step = 3
  if (!config.value?.editable || !canManage.value || step <= activeStep.value) {
    showStep(step)
    return
  }
  const issuesByStep = [workflow.value.targetIssues, workflow.value.relationIssues, workflow.value.assignmentIssues.map(item => item.message)]
  for (let index = 0; index < step; index += 1) {
    if (index === 2 && evaluationMode.value === 'self') continue
    if (issuesByStep[index].length) {
      showStep(index)
      if (index === 1 && !evaluationMode.value) evaluationModeForm.value?.validate().catch(() => {})
      ElMessage.warning(issuesByStep[index][0])
      return
    }
  }
  if (!await saveConfig()) return
  showStep(step)
}

async function goPreparationStep(step) {
  if (busy.value) return
  if (step < 2) {
    if (props.embedded && canEditQuestionnaire.value) {
      if (publicationStore.dirty && !await saveConfig()) return
      emit('step-change', step)
      return
    }
    if (canEditQuestionnaire.value) await router.push({ path: `/hr/projects/${projectId}/editor`, query: { step: String(step + 1) } })
    return
  }
  return goStep(step - 2)
}

function nextStep() {
  return goStep(activeStep.value === 1 && evaluationMode.value === 'self' ? 3 : activeStep.value + 1)
}

async function changeMode(mode) {
  if (busy.value || !canManage.value || !config.value?.editable) return
  if (mode === 'self') {
    const configured = config.value.relations.some(item => item.relationCode !== SELF_RELATION_CODE && item.isEnabled)
    if (configured) {
      modeChanging.value = true
      try {
        await ElMessageBox.confirm('切换为仅自评将关闭其他评价关系，并移除已分配的他评人员。确认切换吗？', '切换为仅自评', { type: 'warning', confirmButtonText: '确认切换', cancelButtonText: '保留当前配置' })
      } catch { return } finally { modeChanging.value = false }
      for (const relation of config.value.relations) {
        if (relation.relationCode !== SELF_RELATION_CODE) publicationStore.updateRelation(relation.relationCode, { isEnabled: false })
      }
    }
  }
  if (mode === 'others' && !config.value.relations.some(item => item.relationCode !== SELF_RELATION_CODE && (item.isEnabled || item.participatesInScore || Number(item.weight) !== 0))) {
    const defaults = [['REL_SUPERVISOR', '60.0000'], ['REL_PEER', '40.0000']]
    if (defaults.every(([code]) => config.value.relations.some(item => item.relationCode === code))) {
      for (const [code, weight] of defaults) {
        publicationStore.updateRelation(code, { isEnabled: true, participatesInScore: true, weight })
      }
    }
  }
  evaluationMode.value = mode
}

async function locateIssue(issue) {
  if (busy.value) return
  const destination = publicationIssueDestination(issue)
  if (destination === 'editor') {
    if (permissionStore.hasPermission('feedback:questionnaire:edit')) await router.push(`/hr/projects/${projectId}/editor`)
    return
  }
  showStep(destination)
  if (destination === 2) {
    await nextTick()
    const index = Number(issue.path?.split('.')[1])
    evaluatorPanel.value?.locate({
      targetUserId: ['EVALUATOR_RELATION_CONFLICT', 'TARGET_SCORING_ASSIGNMENT_REQUIRED', 'TARGET_RELATION_ASSIGNMENT_REQUIRED'].includes(issue.code) ? config.value.targets[index]?.userId : undefined,
      relationCode: ['EVALUATOR_RELATION_CONFLICT', 'TARGET_RELATION_ASSIGNMENT_REQUIRED'].includes(issue.code) ? issue.path?.split('.')[3] : issue.code === 'RELATION_POSITIVE_ASSIGNMENT_REQUIRED' ? config.value.relations[index]?.relationCode : undefined
    })
  }
}

async function completeConfiguration() {
  if (busy.value || !canManage.value || !config.value?.editable) return
  const saved = await saveConfig()
  if (!saved || !saved.isPublishReady || saved.validationIssues.length) return
  ElMessage.success('配置已完成，可在项目列表发布项目')
  await router.push('/hr/projects')
}

onBeforeRouteLeave(async () => {
  if (busy.value) return false
  if (!publicationStore.dirty) return true
  try {
    await ElMessageBox.confirm('当前发布配置有未保存修改，确认离开吗？', '离开配置页', {
      type: 'warning',
      confirmButtonText: '离开',
      cancelButtonText: '继续编辑'
    })
    return true
  } catch {
    return false
  }
})

onMounted(async () => {
  await publicationStore.load(projectId)
  if (!config.value) return
  // 未配置他评关系不代表用户已经选择仅自评，必须由用户明确选择。
  evaluationMode.value = config.value.relations.some(item => item.isEnabled && item.relationCode !== SELF_RELATION_CODE) ? 'others' : ''
  if (!config.value.editable || !canManage.value || config.value.isPublishReady) activeStep.value = 3
  if (config.value.editable && canManage.value && !evaluationMode.value && config.value.targets.length) activeStep.value = 1
  const requestedStep = props.embedded ? props.initialStep - 2 : Number(route.query.step) - 3
  if (config.value.editable && Number.isInteger(requestedStep) && requestedStep >= 0 && requestedStep <= 3) {
    // 跨页请求只能指定目标步骤，仍须通过现有校验，不能绕过保存与发布检查。
    activeStep.value = 0
    await goStep(requestedStep)
  }
})
defineExpose({ goPreparationStep })
onBeforeUnmount(() => publicationStore.reset())
</script>

<template>
  <section v-loading="publicationStore.loading" class="publication-page" :class="{ embedded: props.embedded }">
    <header v-if="!props.embedded" class="publication-header workspace-page-header workspace-detail-header">
      <div class="workspace-detail-heading">
        <el-button
          v-if="config?.editable && permissionStore.hasPermission('feedback:questionnaire:edit')"
          class="workspace-detail-back" text size="small" aria-label="返回问卷编辑" title="返回问卷编辑"
          :disabled="busy"
          @click="router.push(`/hr/projects/${projectId}/editor`)"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="m10 6-6 6 6 6M4 12h16" />
          </svg>
          <span>返回</span>
        </el-button>
        <el-button v-else class="workspace-detail-back" text size="small" aria-label="返回项目列表" title="返回项目列表" :disabled="publicationStore.loading || busy" @click="router.push('/hr/projects')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="m10 6-6 6 6 6M4 12h16" />
          </svg>
          <span>返回</span>
        </el-button>
        <el-divider direction="vertical" class="workspace-detail-divider" />
        <div class="workspace-detail-title">
          <h1>{{ config && !config.editable ? '发布详情' : '人员关系与发布' }}</h1>
          <p class="workspace-detail-project">
            <span class="workspace-detail-project-label">所属项目</span>
            <span class="workspace-detail-project-name" :title="config?.projectName || '评价项目'">{{ config?.projectName || '评价项目' }}</span>
          </p>
        </div>
      </div>
      <div v-if="config" class="header-status">
        <span v-if="publicationStore.dirty" class="dirty-state">有未保存修改</span>
        <span v-else-if="publicationStore.lastSavedAt" class="saved-state">配置已保存</span>
        <el-tag size="small" :type="config.editable ? 'warning' : 'success'">
          {{ config.editable ? '准备阶段' : '已冻结只读' }}
        </el-tag>
      </div>
    </header>

    <PublicationDetails v-if="config && !config.editable" :config="config" />
    <template v-if="config?.editable">
      <ProjectPreparationSteps
        class="publication-steps"
        :active="activeStep + 2"
        :completed="completedSteps"
        :skipped="evaluationMode === 'self' ? [4] : []"
        :disabled="busy || publicationStore.loading"
        :disabled-steps="canEditQuestionnaire ? [] : [0, 1]"
        :descriptions="preparationDescriptions"
        @select="goPreparationStep"
      />
      <div ref="stepContent" class="step-content">
      <el-card v-show="activeStep === 0" shadow="never">
        <TargetSelectorPanel
          :load-departments="loadTargetDepartments"
          :load-people="loadTargetPeople"
          :can-browse="config.editable && canManage"
          :selected-targets="config.targets"
          :editable="config.editable && canManage && !busy"
          @add="publicationStore.addTarget"
          @remove="publicationStore.removeTarget"
        />
      </el-card>

      <el-card v-show="activeStep === 1" shadow="never">
        <el-form ref="evaluationModeForm" :model="{ evaluationMode }" class="evaluation-mode" label-position="top">
          <el-form-item label="本轮如何评价？" prop="evaluationMode" :rules="[{ required: true, message: '请选择评价方式', trigger: 'change' }]">
            <el-radio-group :model-value="evaluationMode" :disabled="!config.editable || !canManage || busy" @change="changeMode">
              <el-radio-button value="others">自评 + 他人评价</el-radio-button>
              <el-radio-button value="self">仅自评</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <p v-if="evaluationMode === 'self'">例如：张三填写问卷评价自己的表现。张三既是被评价人，也是评价人，评价关系为“自评”。</p>
          <p v-else-if="evaluationMode === 'others'">例如：李四作为上级评价张三。张三是被评价人，李四是评价人，“上级”是评价关系。</p>
        </el-form>
        <el-alert v-if="evaluationMode === 'self'" title="每名被评价人只填写自己的问卷，无需分配其他评价人。下一步直接检查发布条件。" type="info" :closable="false" show-icon />
        <RelationConfigPanel
          v-else-if="evaluationMode === 'others'"
          :relations="config.relations"
          :editable="config.editable && canManage && !busy"
          @update="publicationStore.updateRelation"
          @add="publicationStore.addCustomRelation"
          @remove="publicationStore.removeRelation"
          @move="publicationStore.moveRelation"
        />
      </el-card>

      <el-card v-show="activeStep === 2" shadow="never">
        <el-alert v-if="evaluationMode === 'self'" title="本轮仅自评，自评任务自动添加，无需分配他人。" type="info" :closable="false" show-icon />
        <EvaluatorSelectionPanel
          v-else
          ref="evaluatorPanel"
          :active="activeStep === 2"
          :summaries="workflow.targetSummaries"
          :assignment-issues="workflow.assignmentIssues"
          :targets="config.targets"
          :relations="config.relations"
          :selections="config.evaluatorSelections"
          :participants="participantDirectory"
          :load-departments="loadTargetDepartments"
          :load-people="loadTargetPeople"
          @remember-person="publicationStore.rememberParticipant"
          :editable="config.editable && canManage && !busy"
          @set-evaluators="publicationStore.setEvaluatorIds"
        />
      </el-card>

      <el-card v-show="activeStep === 3" shadow="never">
        <PublicationPreviewPanel
          :preview="config.preview"
          :issues="config.validationIssues"
          :ready="config.isPublishReady"
          :targets="config.targets"
          :participants="participantDirectory"
          :stale="publicationStore.dirty"
          :editable="config.editable && canManage && !busy"
          :can-edit-questionnaire="config.editable && permissionStore.hasPermission('feedback:questionnaire:edit') && !busy"
          @locate="locateIssue"
        />
        <PublicationConfigurationReview v-if="activeStep === 3" :config="config" :can-edit-questionnaire="config.editable && canEditQuestionnaire && !busy" :can-manage="config.editable && canManage && !busy" @edit="goPreparationStep" />
      </el-card>
      </div>
      <div v-if="config.editable" class="action-bar">
        <div aria-live="polite">
          <strong>{{ `第 ${activeStep + 3} 步：${PUBLICATION_STEPS[activeStep]}` }}</strong>
          <span>{{ activeStep === 3 ? publicationStore.dirty ? '配置已修改，请保存并重新检查。' : '完成配置后返回列表，项目保持准备阶段，可在列表中正式发布。' : currentIssues[0] || '本步已完成，可以继续；返回修改会保留当前配置。' }}</span>
        </div>
        <div class="action-buttons">
          <el-button v-if="activeStep > 0 || canEditQuestionnaire" :disabled="busy" @click="activeStep === 0 ? goPreparationStep(1) : goStep(activeStep === 3 && evaluationMode === 'self' ? 1 : activeStep - 1)">上一步</el-button>
          <el-button
            v-if="canManage"
            :loading="publicationStore.saving"
            :disabled="publicationStore.publishing || modeChanging"
            @click="saveConfig"
          >
            {{ activeStep === 3 && publicationStore.dirty ? '保存并重新检查' : '保存配置' }}
          </el-button>
          <el-button v-if="activeStep < 3" type="primary" :loading="publicationStore.saving" :disabled="publicationStore.publishing || modeChanging" @click="nextStep">{{ nextLabel }}</el-button>
          <el-button
            v-if="activeStep === 3 && canManage"
            type="primary"
            :loading="publicationStore.saving"
            :disabled="busy"
            @click="completeConfiguration"
          >
            完成配置
          </el-button>
        </div>
      </div>
    </template>
  </section>
</template>

<style scoped>
.embedded.publication-page { width: 100%; min-width: 0; height: 100%; min-height: 0; max-width: none; margin: 0; padding: 0; box-sizing: border-box; display: grid; grid-template-rows: auto minmax(0, 1fr) auto; gap: 16px; }
.embedded .step-content { overflow: auto; min-height: 0; }
.embedded .action-bar { position: static; margin: 0; }

.publication-page { display: flex; flex-direction: column; gap: 24px; max-width: 1440px; margin: auto; padding-top: 12px; min-height: calc(100dvh - 110px); }
.publication-header { flex-wrap: nowrap; gap: 12px; min-height: 54px; padding: 10px 14px; }
.publication-header .workspace-detail-heading { flex: 1; }
.publication-header .workspace-detail-back { height: 30px; padding: 4px 6px; }
.publication-header .workspace-detail-divider { height: 26px; margin-inline: 10px; }
.publication-header .workspace-detail-title { display: flex; flex: 0 1 auto; align-items: center; gap: 14px; }
.publication-header h1 { flex: none; font-size: 17px; }
.publication-header .workspace-detail-project { min-width: 0; margin: 0; }
.publication-steps { position: sticky; top: 56px; z-index: 9; }
.step-content { flex: 1; min-width: 0; scroll-margin-top: 190px; }
.evaluation-mode p { margin: 0 0 18px; color: var(--fb-text-muted, #64748b); font-size: 13px; }
.evaluation-mode:deep(.el-form-item) { margin-bottom: 10px; }
.header-status, .action-bar, .action-buttons { display: flex; align-items: center; gap: 14px; }
.header-status { flex-shrink: 0; flex-wrap: wrap; }
.action-bar { justify-content: space-between; }
.dirty-state { color: #e6a23c; font-size: 13px; }
.saved-state { color: #67c23a; font-size: 13px; }
.action-bar { position: sticky; bottom: 12px; z-index: 8; padding: 14px 18px; border: 1px solid var(--fb-primary-border, #dbeafe); border-radius: 10px; background: var(--fb-surface-floating, rgb(255 255 255 / 96%)); box-shadow: 0 8px 28px rgb(15 23 42 / 12%); backdrop-filter: blur(8px); }
.action-bar > div:first-child { display: grid; gap: 3px; }
.action-bar span { color: var(--fb-text-muted, #64748b); font-size: 12px; }
@media (max-width: 760px) {
  .publication-header { align-items: flex-start; flex-wrap: wrap; }
  .publication-header .workspace-detail-title { display: block; }
  .publication-header .workspace-detail-project { margin-top: 2px; }
  .publication-steps { position: static; overflow-x: auto; }
  .action-bar { align-items: flex-start; flex-direction: column; }
  .action-buttons { width: 100%; }
  .action-buttons:deep(.el-button) { flex: 1; }
}
</style>
