import { defineConfig } from '@playwright/test'
import { resolve } from 'node:path'

/**
 * Browser end-to-end tests against the real backend and frontend, fully offline:
 * the backend runs on its own port with an isolated data dir seeded from the captured NASA
 * fixtures (tests/e2e_seed.py), so your own data/ is never touched. Uses the installed
 * Microsoft Edge (no browser download).
 */
const API_PORT = 8100
const WEB_PORT = 5180
const DATA_DIR = resolve(import.meta.dirname, 'e2e', '.data')

export default defineConfig({
  testDir: './e2e',
  testIgnore: '**/screens.spec.ts',
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: `http://localhost:${WEB_PORT}`,
    channel: 'msedge',
    viewport: { width: 1440, height: 900 },
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: `uv run python -m tests.e2e_seed "${DATA_DIR}" && uv run uvicorn mars_explorer.api.app:app --port ${API_PORT}`,
      cwd: resolve(import.meta.dirname, '..', 'backend'),
      url: `http://127.0.0.1:${API_PORT}/api/health`,
      env: { MARS_DATA_DIR: DATA_DIR, ANTHROPIC_API_KEY: '', MARS_LOG_LEVEL: 'WARNING' },
      timeout: 120_000,
      reuseExistingServer: false,
    },
    {
      command: `npm run dev -- --port ${WEB_PORT} --strictPort`,
      url: `http://localhost:${WEB_PORT}`,
      env: { MARS_API_TARGET: `http://127.0.0.1:${API_PORT}` },
      timeout: 60_000,
      reuseExistingServer: false,
    },
  ],
})
