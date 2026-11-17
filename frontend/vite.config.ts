import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// E2E runs use their own backend port (see playwright.config.ts).
const apiTarget = process.env.MARS_API_TARGET ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    // The browser only talks to Vite; Vite forwards /api to the FastAPI backend.
    proxy: { '/api': { target: apiTarget, changeOrigin: false } },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    include: ['src/**/*.test.{ts,tsx}'],
  },
})
