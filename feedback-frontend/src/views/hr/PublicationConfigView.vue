<script setup>
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'

import EvaluatorSelectionPanel from '@/components/feedback/publication/EvaluatorSelectionPanel.vue'
import PublicationPreviewPanel from '@/components/feedback/publication/PublicationPreviewPanel.vue'
import RelationConfigPanel from '@/components/feedback/publication/RelationConfigPanel.vue'
import TargetSelectorPanel from '@/components/feedback/publication/TargetSelectorPanel.vue'
import { usePermissionStore } from '@/stores/permission'
import { usePublicationConfigStore } from '@/stores/publicationConfig'

const route = useRoute()
const router = useRouter()
const permissionStore = usePermissionStore()
const publicationStore = usePublicationConfigStore()
const projectId = Number(route.params.projectId)
const config = computed(() => publicationStore.config)
const canManage = computed(() => permissionStore.hasPermission('feedback:participant:manage'))
const canPublishPermission = computed(() => permissionStore.hasPermission('feedback:project:publish'))
const participantDirectory = computed(() => Array.from(publicationStore.participantDirectory.values()))
const canPublish = computed(
  () =>
    publicationStore.editable &&
    canPublishPermission.value &&
    !publicationStore.dirty &&
    config.value?.isPublishReady
)

async function loadCandidates({ pageNum = 1, keyword = publicationStore.candidateKeyword } = {}) {
  if (!canManage.value) return
  await publicationStore.loadCandidates({ pageNum, keyword })
}

async function saveConfig() {
  if (publicationStore.saving) return
  try {
    const saved = await publicationStore.save()
    if (!saved) return
    if (saved.validationIssues.length) {
      ElMessage.success(`配置已保存；仍有${saved.validationIssues.length}项发布前检查待处理`)
    } else {
      ElMessage.success('配置已保存，发布前检查已通过')
    }
  } catch (error) {
    if (!error.status) ElMessage.warning(error.message)
  }
}

async function publish() {
  if (publicationStore.publishing || !canPublish.value) return
  const preview = config.value.preview
  try {
    await ElMessageBox.confirm(
      `将冻结${preview.targetCount}名被评价人的配置并生成${preview.assignmentCount}项任务。发布后不可修改，确认继续吗？`,
      '确认发布项目',
      {
        type: 'warning',
        confirmButtonText: '确认发布',
        cancelButtonText: '返回检查'
      }
    )
    const result = await publicationStore.publish()
    if (result) ElMessage.success(result.alreadyPublished ? '项目已经发布，已返回冻结结果' : '项目发布成功')
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    if (!error.status) ElMessage.warning(error.message)
  }
}

onBeforeRouteLeave(async () => {
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
  await loadCandidates()
})
onBeforeUnmount(() => publicationStore.reset())
</script>

<template>
  <section v-loading="publicationStore.loading" class="publication-page">
    <header class="page-header">
      <div class="heading-block">
        <el-button link @click="router.push('/hr/projects')">返回项目列表</el-button>
        <div>
          <p>{{ config?.projectName || '评价项目' }}</p>
          <h1>人员关系与发布</h1>
        </div>
      </div>
      <div v-if="config" class="header-status">
        <span v-if="publicationStore.dirty" class="dirty-state">有未保存修改</span>
        <span v-else-if="publicationStore.lastSavedAt" class="saved-state">配置已保存</span>
        <el-tag :type="config.editable ? 'warning' : 'success'">
          {{ config.editable ? '准备阶段' : '已冻结只读' }}
        </el-tag>
      </div>
    </header>

    <el-alert
      v-if="config && !config.editable"
      title="项目已经发布，以下问卷版本、人员快照、关系和任务来源均为冻结只读信息。"
      type="success"
      :closable="false"
      show-icon
    />
    <el-alert
      v-else
      title="先保存配置并处理后端返回的全部问题，再执行不可逆发布。"
      type="info"
      :closable="false"
      show-icon
    />

    <template v-if="config">
      <el-card shadow="never">
        <TargetSelectorPanel
          :rows="publicationStore.candidateRows"
          :total="publicationStore.candidateTotal"
          :page-num="publicationStore.candidatePageNum"
          :page-size="publicationStore.candidatePageSize"
          :selected-targets="config.targets"
          :loading="publicationStore.candidatesLoading"
          :editable="config.editable && canManage"
          @search="loadCandidates({ pageNum: 1, keyword: $event })"
          @page-change="loadCandidates({ pageNum: $event })"
          @add="publicationStore.addTarget"
          @remove="publicationStore.removeTarget"
        />
      </el-card>

      <el-card shadow="never">
        <RelationConfigPanel
          :relations="config.relations"
          :editable="config.editable && canManage"
          @update="publicationStore.updateRelation"
          @add="publicationStore.addCustomRelation"
          @remove="publicationStore.removeRelation"
          @move="publicationStore.moveRelation"
        />
      </el-card>

      <el-card shadow="never">
        <EvaluatorSelectionPanel
          :targets="config.targets"
          :relations="config.relations"
          :selections="config.evaluatorSelections"
          :participants="participantDirectory"
          :candidate-rows="publicationStore.candidateRows"
          :candidate-total="publicationStore.candidateTotal"
          :candidate-page-num="publicationStore.candidatePageNum"
          :candidate-page-size="publicationStore.candidatePageSize"
          :loading="publicationStore.candidatesLoading"
          :editable="config.editable && canManage"
          @search="loadCandidates({ pageNum: 1, keyword: $event })"
          @page-change="loadCandidates({ pageNum: $event })"
          @set-evaluators="publicationStore.setEvaluatorIds"
        />
      </el-card>

      <el-card shadow="never">
        <PublicationPreviewPanel
          :preview="config.preview"
          :issues="config.validationIssues"
          :ready="config.isPublishReady"
        />
      </el-card>

      <div v-if="config.editable" class="action-bar">
        <div>
          <strong>发布后不可修改</strong>
          <span>任务只会在后端发布事务内生成。</span>
        </div>
        <div class="action-buttons">
          <el-button
            v-if="canManage"
            :loading="publicationStore.saving"
            :disabled="publicationStore.publishing"
            @click="saveConfig"
          >
            保存配置
          </el-button>
          <el-button
            v-if="canPublishPermission"
            type="primary"
            :loading="publicationStore.publishing"
            :disabled="!canPublish"
            @click="publish"
          >
            发布项目
          </el-button>
        </div>
      </div>
    </template>
  </section>
</template>

<style scoped>
.publication-page { display: grid; gap: 16px; padding-bottom: 96px; }
.page-header, .heading-block, .header-status, .action-bar, .action-buttons { display: flex; align-items: center; gap: 14px; }
.page-header, .action-bar { justify-content: space-between; }
.heading-block p, .heading-block h1 { margin: 0; }
.heading-block p { margin-bottom: 3px; color: #64748b; font-size: 13px; }
.heading-block h1 { color: #111827; font-size: 22px; }
.dirty-state { color: #e6a23c; font-size: 13px; }
.saved-state { color: #67c23a; font-size: 13px; }
.action-bar { position: sticky; bottom: 12px; z-index: 8; padding: 14px 18px; border: 1px solid #dbeafe; border-radius: 10px; background: rgb(255 255 255 / 96%); box-shadow: 0 8px 28px rgb(15 23 42 / 12%); backdrop-filter: blur(8px); }
.action-bar > div:first-child { display: grid; gap: 3px; }
.action-bar span { color: #64748b; font-size: 12px; }
@media (max-width: 760px) {
  .page-header, .action-bar { align-items: flex-start; flex-direction: column; }
  .header-status { flex-wrap: wrap; }
  .action-buttons { width: 100%; }
  .action-buttons :deep(.el-button) { flex: 1; }
}
</style>
