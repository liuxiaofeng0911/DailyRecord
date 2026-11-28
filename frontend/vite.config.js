import { readFileSync } from 'node:fs'
import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig, loadEnv } from 'vite'

const pkg = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf-8'))

export default defineConfig(({ mode }) => {
  // 本地调试的端口与后端地址优先取仓库根 .env（不入库），仓库内只保留通用默认值
  const rootEnv = loadEnv(mode, fileURLToPath(new URL('..', import.meta.url)), '')
  const devPort = Number(process.env.VITE_DEV_PORT || rootEnv.VITE_DEV_PORT || 5173)
  const apiTarget = process.env.VITE_API_TARGET || `http://localhost:${rootEnv.API_PORT || 8000}`
  const immichTarget = `http://localhost:${rootEnv.IMMICH_PORT || 2283}`

  return {
    plugins: [vue()],
    define: {
      __APP_VERSION__: JSON.stringify(process.env.VITE_APP_VERSION || pkg.version),
    },
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    css: {
      preprocessorOptions: {
        less: { javascriptEnabled: true },
      },
    },
    server: {
      port: devPort,
      strictPort: true,
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
        },
        '/immich': {
          target: immichTarget,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/immich/, ''),
        },
      },
    },
    build: {
      outDir: 'dist',
      chunkSizeWarningLimit: 1500,
    },
  }
})
