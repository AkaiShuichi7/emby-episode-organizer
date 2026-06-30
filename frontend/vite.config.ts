import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      'naive-ui/dist/preset.css': fileURLToPath(new URL('./src/styles/naive-ui-preset.css', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8899', changeOrigin: true },
      '/openapi.json': { target: 'http://localhost:8899', changeOrigin: true },
    },
  },
})
