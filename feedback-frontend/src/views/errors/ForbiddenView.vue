<script setup>
import { useRouter } from 'vue-router'

import { usePermissionStore } from '@/stores/permission'

const router = useRouter()
const permissionStore = usePermissionStore()
</script>

<template>
  <el-result icon="warning" title="无权访问当前页面" sub-title="可以返回已有权限的工作台；如需访问此页，请联系系统管理员。">
    <template #extra>
      <el-button type="primary" @click="router.replace(permissionStore.defaultPath())">
        返回可用工作台
      </el-button>
    </template>
  </el-result>
</template>
