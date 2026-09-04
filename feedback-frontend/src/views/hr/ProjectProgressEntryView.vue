<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const formRef = ref()
const form = reactive({ projectId: null })

function validateProjectId(_rule, value, callback) {
  if (!Number.isInteger(value) || value < 1) return callback(new Error('项目ID必须为正整数'))
  callback()
}

const rules = {
  projectId: [{ validator: validateProjectId, trigger: 'change' }]
}

async function openProgress() {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  await router.push(`/hr/projects/${form.projectId}/progress`)
}
</script>

<template>
  <section class="progress-entry-page">
    <header class="workspace-page-header">
      <div><h1 class="page-heading">评价进度</h1>
      <p class="page-description">输入项目编号，查看你有权限访问的评价进度。</p></div>
    </header>
    <el-card shadow="never" class="entry-card">
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
        <el-form-item label="项目ID" prop="projectId">
          <el-input-number
            v-model="form.projectId"
            :min="1"
            :step="1"
            step-strictly
            :controls="false"
            placeholder="输入有权查看的项目ID"
            @keyup.enter="openProgress"
          />
        </el-form-item>
        <el-button type="primary" @click="openProgress">查看评价进度</el-button>
      </el-form>
    </el-card>
  </section>
</template>

<style scoped>
.progress-entry-page { display: grid; max-width: 720px; gap: 20px; }
.progress-entry-page h1 { margin: 0 0 8px; color: var(--fb-text-primary, #0f172a); }
.progress-entry-page p { margin: 0; color: var(--fb-text-muted, #64748b); line-height: 1.7; }
.entry-card:deep(.el-input-number) { width: 100%; }
</style>
