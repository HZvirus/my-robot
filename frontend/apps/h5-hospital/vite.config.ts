import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const KONG = process.env.KONG_URL ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': { target: KONG, changeOrigin: true },
      '/auth': { target: KONG, changeOrigin: true },
      '/ws': { target: KONG, changeOrigin: true, ws: true },
    },
  },
})
