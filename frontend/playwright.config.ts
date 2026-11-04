import { defineConfig, devices } from '@playwright/test';

export const WEB_URL = process.env.E2E_WEB_URL || 'http://127.0.0.1:3100';
export const API_URL = process.env.E2E_API_URL || 'http://127.0.0.1:8100';

export default defineConfig({
  testDir: './e2e',
  testMatch: '**/*.spec.ts',
  globalSetup: './e2e/global-setup.ts',
  timeout: 30_000,
  expect: { timeout: 8_000 },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 3 : 2,
  reporter: [['list'], ['html', { outputFolder: 'playwright-report', open: 'never' }], ['junit', { outputFile: 'test-results/e2e-junit.xml' }]],
  outputDir: 'test-results/playwright',
  use: {
    baseURL: WEB_URL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    ...devices['Desktop Chrome'],
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
