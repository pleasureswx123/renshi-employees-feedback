import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  test: {
    environment: 'jsdom',
    // 按浏览器构建链解析async-validator，避免Node外部化导入吞掉表单校验错误。
    server: { deps: { inline: ['element-plus'] } },
    setupFiles: ['./tests/setup.js'],
    exclude: ['tests/e2e/**', 'tests/live-e2e/**', 'node_modules/**', 'dist/**'],
    clearMocks: true,
    restoreMocks: true
  }
})
