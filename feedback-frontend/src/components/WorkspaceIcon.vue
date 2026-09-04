<script setup>
import { computed } from 'vue'

const props = defineProps({ name: { type: String, required: true } })
const paths = {
  project: 'M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v10H3Z',
  report: 'M4 3v18h17M8 16v-5m5 5V7m5 9v-8',
  answers: 'M6 3h9l4 4v14H6ZM14 3v5h5M9 12h7m-7 4h7',
  todos: 'M9 5H5v16h15V5h-4M9 3h7v5H9Zm0 11 2 2 5-5',
  history: 'M4 10a8 8 0 1 1 1 7M4 4v6h6m2-4v6l4 2',
  collapse: 'M4 5h16M4 12h7M4 19h16m1-11-4 4 4 4',
  expand: 'M4 5h16M4 12h7M4 19h16m-6-11 4 4-4 4',
  menu: 'M4 6h16M4 12h16M4 18h16',
  search: 'M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0Zm-2 5 6 6',
  refresh: 'M20 7a8 8 0 1 0 1 8M20 3v5h-5',
  plus: 'M12 5v14M5 12h14',
  logout: 'M9 3H4v18h5m5-14 5 5-5 5m-5-5h10',
  user: 'M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0ZM4 21v-2a8 8 0 0 1 16 0v2'
}
const path = computed(() => paths[props.name] || paths.project)
</script>

<template>
  <svg class="workspace-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path :d="path" />
  </svg>
</template>

<style scoped>
.workspace-icon { width: 1.15em; height: 1.15em; flex-shrink: 0; vertical-align: middle; }
</style>
