import { defineConfig } from '@playwright/test'

/**
 * Portfolio screenshots of the running app with YOUR real data (start it first with
 * .\scripts\dev.ps1). Writes PNGs to docs/media/. Not part of the test suite.
 */
export default defineConfig({
  testDir: './e2e',
  testMatch: '**/screens.spec.ts',
  timeout: 120_000,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: process.env.MARS_APP_URL ?? 'http://localhost:5173',
    channel: 'msedge',
    viewport: { width: 1440, height: 900 },
  },
})
