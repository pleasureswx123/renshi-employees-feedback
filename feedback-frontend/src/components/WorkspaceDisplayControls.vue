<script setup>
import MaximizeIcon from '@iconify-vue/lucide/maximize'
import MinimizeIcon from '@iconify-vue/lucide/minimize'
import MoonIcon from '@iconify-vue/lucide/moon'
import SunIcon from '@iconify-vue/lucide/sun'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { useWorkspaceUiStore } from '@/stores/workspaceUi'

const ui = useWorkspaceUiStore()
const isFullscreen = ref(false)
const fullscreenSupported = ref(false)
const fullscreenPending = ref(false)
const fullscreenLabel = computed(() => !fullscreenSupported.value ? '当前浏览器不支持全屏' : isFullscreen.value ? '退出全屏' : '进入全屏')
const themeLabel = computed(() => ui.isDark ? '切换到浅色模式' : '切换到深色模式')

function syncFullscreen() {
  isFullscreen.value = Boolean(document.fullscreenElement)
  fullscreenSupported.value = Boolean(document.fullscreenEnabled && document.documentElement.requestFullscreen && document.exitFullscreen)
}

async function toggleFullscreen() {
  if (!fullscreenSupported.value || fullscreenPending.value) return
  fullscreenPending.value = true
  try {
    if (document.fullscreenElement) await document.exitFullscreen()
    else await document.documentElement.requestFullscreen()
  } catch {
    ElMessage.warning('全屏切换失败，请重试或检查浏览器是否允许全屏')
  } finally {
    syncFullscreen()
    fullscreenPending.value = false
  }
}

onMounted(() => {
  syncFullscreen()
  // 按Esc或浏览器控制退出后，图标同步真实全屏状态。
  document.addEventListener('fullscreenchange', syncFullscreen)
})
onBeforeUnmount(() => document.removeEventListener('fullscreenchange', syncFullscreen))
</script>

<template>
  <div class="workspace-display-controls" role="group" aria-label="显示设置">
    <el-tooltip :content="fullscreenLabel" placement="bottom">
      <span class="display-control-wrap">
        <el-button text class="display-control" :aria-label="fullscreenLabel" :aria-pressed="isFullscreen"
          :disabled="!fullscreenSupported || fullscreenPending" :loading="fullscreenPending" @click="toggleFullscreen">
          <component :is="isFullscreen ? MinimizeIcon : MaximizeIcon" v-if="!fullscreenPending" aria-hidden="true" />
        </el-button>
      </span>
    </el-tooltip>
    <el-tooltip :content="themeLabel" placement="bottom">
      <el-button text class="display-control" :aria-label="themeLabel" :aria-pressed="ui.isDark" @click="ui.toggleTheme">
        <component :is="ui.isDark ? SunIcon : MoonIcon" aria-hidden="true" />
      </el-button>
    </el-tooltip>
  </div>
</template>

<style scoped>
.workspace-display-controls { display: flex; flex-shrink: 0; align-items: center; gap: 4px; }
.display-control-wrap { display: inline-flex; }
.display-control {
  --el-button-text-color: #d6e1ef;
  --el-button-hover-text-color: #fff;
  --el-button-active-text-color: #fff;
  --el-button-disabled-text-color: #8595ab;
  --el-fill-color-light: #34455e;
  --el-fill-color: #3c506b;
  width: 32px; height: 32px; margin: 0; padding: 7px; font-size: 18px;
}
.display-control:focus-visible { outline: 2px solid #93c5fd; outline-offset: 2px; }
.display-control svg { width: 18px; height: 18px; }
</style>
