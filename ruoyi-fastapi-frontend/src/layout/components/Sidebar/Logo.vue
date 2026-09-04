<template>
  <div class="sidebar-logo-container" :class="{ 'collapse': collapse }">
    <transition name="sidebarLogoFade">
      <router-link v-if="collapse" key="collapse" class="sidebar-logo-link" to="/" :title="title" :aria-label="title">
        <img v-if="logo" :src="logo" alt="" class="sidebar-logo" />
        <h1 v-else class="sidebar-title">{{ brand.name }}</h1>
      </router-link>
      <router-link v-else key="expand" class="sidebar-logo-link" to="/" :title="title" :aria-label="title">
        <img v-if="logo" :src="logo" alt="" class="sidebar-logo" />
        <div class="sidebar-brand-copy"><h1 class="sidebar-title">{{ brand.name }}</h1><small>{{ brand.edition }}</small></div>
      </router-link>
    </transition>
  </div>
</template>

<script setup>
import useSettingsStore from '@/store/modules/settings'
import variables from '@/assets/styles/variables.module.scss'
import { brand } from '@/config/brand'

defineProps({
  collapse: {
    type: Boolean,
    required: true
  }
})

const title = brand.title;
const logo = brand.logo;
const settingsStore = useSettingsStore();
const sideTheme = computed(() => settingsStore.sideTheme);

// 获取Logo背景色
const getLogoBackground = computed(() => {
  if (settingsStore.isDark) {
    return 'var(--sidebar-bg)';
  }
  if (settingsStore.navType == 3) {
    return variables.menuLightBg
  }
  return sideTheme.value === 'theme-dark' ? variables.menuBg : variables.menuLightBg;
});

// 获取Logo文字颜色
const getLogoTextColor = computed(() => {
  if (settingsStore.isDark) {
    return 'var(--sidebar-logo-text)'
  }
  if (settingsStore.navType == 3) {
    return variables.menuLightText
  }
  return sideTheme.value === 'theme-dark' ? '#fff' : variables.menuLightText;
});
</script>

<style lang="scss" scoped>
.sidebarLogoFade-enter-active {
  transition: opacity 1.5s;
}

.sidebarLogoFade-enter,
.sidebarLogoFade-leave-to {
  opacity: 0;
}

.sidebar-logo-container {
  position: relative;
  height: 50px;
  line-height: 50px;
  background: v-bind(getLogoBackground);
  text-align: center;
  overflow: hidden;

  & .sidebar-logo-link {
    height: 100%;
    width: 100%;

    & .sidebar-logo {
      width: 34px;
      height: 34px;
      vertical-align: middle;
      margin-right: 10px;
    }

    & .sidebar-title {
      display: inline-block;
      margin: 0;
      color: v-bind(getLogoTextColor);
      font-weight: 600;
      line-height: 50px;
      font-size: 20px;
      letter-spacing: 2px;
      font-family: Avenir, Helvetica Neue, Arial, Helvetica, sans-serif;
      vertical-align: middle;
    }
  }

  .sidebar-brand-copy { display: inline-flex; align-items: baseline; gap: 10px; vertical-align: middle; }
  .sidebar-brand-copy small { color: v-bind(getLogoTextColor); opacity: .65; font-size: 11px; font-weight: 400; }

  &.collapse {
    .sidebar-logo {
      margin-right: 0px;
    }
  }
}
</style>
