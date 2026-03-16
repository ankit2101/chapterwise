// @ts-check
import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for ChapterWise E2E tests.
 *
 * Prerequisites before running:
 *   1. Flask backend running:  python app.py            (port 5000)
 *   2. Vite dev server:        cd frontend && npm run dev (port 5173)
 *   OR the built SPA served by Flask on port 5000.
 *
 * Quick start:
 *   cd e2e && npm install && npx playwright install chromium
 *   npm test
 */

const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';
const API_URL  = process.env.API_URL  || 'http://localhost:5000';

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,       // tests share DB state; run serially per file
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,                 // single worker to avoid DB races
  reporter: [
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
    ['list'],
  ],

  use: {
    baseURL: BASE_URL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    // Pass API base URL to tests via env
    extraHTTPHeaders: { 'x-test-mode': '1' },
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    // Uncomment to add more browsers:
    // { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
    // { name: 'Mobile Chrome', use: { ...devices['Pixel 5'] } },
  ],

  // Global timeout per test
  timeout: 30_000,
  expect: { timeout: 8_000 },
});

export { BASE_URL, API_URL };
