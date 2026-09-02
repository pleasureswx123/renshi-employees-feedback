<script setup>
import { useRouter } from 'vue-router'

import { usePermissionStore } from '@/stores/permission'

const router = useRouter()
const permissionStore = usePermissionStore()
</script>

<template>
  <el-result icon="warning" title="暂无评价平台权限" sub-title="请联系系统管理员配置对应的 HR 或员工权限。">
    <template #extra>
      <el-button type="primary" @click="router.replace(permissionStore.defaultPath())">
        返回可用工作台
      </el-button>
    </template>
  </el-result>
</template>
