import { defineConfig, devices } from '@playwright/test'
export default defineConfig({
  testDir: './tests',
  testMatch: /mobile-sidebar\.spec\.ts/,
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  use: { trace: 'retain-on-failure', screenshot: 'only-on-failure' },
  projects: [{ name: 'mobile', use: { ...devices['iPhone 12'] } }],
})
