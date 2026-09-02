import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd())

  return {
    plugins: [vue()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url))
      }
    },
    server: {
      host: '127.0.0.1',
      port: 5174,
      proxy: {
        '/dev-api': {
          target:
            process.env.VITE_APP_PROXY_TARGET ||
            env.VITE_APP_PROXY_TARGET ||
            'http://127.0.0.1:9099',
          changeOrigin: true,
          rewrite: path => path.replace(/^\/dev-api/, '')
        }
      }
    },
    preview: {
      host: '127.0.0.1',
      port: 4174
    },
    build: {
      outDir: 'dist',
      assetsDir: 'assets',
      sourcemap: false
    }
  }
})
