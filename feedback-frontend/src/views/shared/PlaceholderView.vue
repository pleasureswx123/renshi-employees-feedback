<script setup>
defineProps({
  title: { type: String, required: true },
  description: { type: String, required: true }
})
</script>

<template>
  <el-card class="page-card" shadow="never">
    <h1 class="page-heading">{{ title }}</h1>
    <p class="page-description">{{ description }}</p>
    <el-alert
      class="phase-alert"
      title="当前为工程基线阶段"
      description="本页面只证明独立工程、登录恢复和权限路由已经接通，不代表后续评价业务功能已经完成。"
      type="info"
      :closable="false"
      show-icon
    />
  </el-card>
</template>

<style scoped>
.phase-alert {
  margin-top: 28px;
}
</style>
