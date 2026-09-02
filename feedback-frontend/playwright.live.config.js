import { fileURLToPath } from 'node:url'
import { defineConfig } from '@playwright/test'

const backend = fileURLToPath(new URL('../ruoyi-fastapi-backend', import.meta.url))
const python = process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python'

export default defineConfig({
  testDir: './tests/live-e2e',
  workers: 1,
  retries: 0,
  timeout: 120000,
  reporter: 'list',
  outputDir: '../output/playwright/p6-live',
  use: { baseURL: 'http://127.0.0.1:5177', locale: 'zh-CN', trace: 'off', screenshot: 'only-on-failure' },
  webServer: [
    {
      command: `"${python}" scripts/feedback_p6_e2e_server.py`, cwd: backend,
      url: 'http://127.0.0.1:9097/transport/crypto/frontend-config', reuseExistingServer: false, timeout: 120000
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 5177 --strictPort',
      env: { VITE_APP_PROXY_TARGET: 'http://127.0.0.1:9097' },
      url: 'http://127.0.0.1:5177/login', reuseExistingServer: false, timeout: 120000
    }
  ]
})
