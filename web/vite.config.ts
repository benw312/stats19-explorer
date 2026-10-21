import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// Dev: the API runs on :8000 (stats19 serve; STATS19_API_URL overrides it); the basemap is served from data/basemap
// via a symlink at public/basemap (gitignored). In production Caddy serves both.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Keep the browser's Host: the API's write guard (V5 schemes) checks Origin against it.
      '/api': { target: process.env.STATS19_API_URL ?? 'http://127.0.0.1:8000', changeOrigin: false },
    },
  },
  worker: {
    format: 'es',
  },
  build: {
    // The lazy map chunk (MapLibre + Terra Draw, ~310 kB gz) is the only large one;
    // first paint stays ~90 kB gz.
    chunkSizeWarningLimit: 1300,
  },
  test: {
    environment: 'jsdom',
  },
})
