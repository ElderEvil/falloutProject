import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests/performance',
  fullyParallel: false,
  retries: 0,
  workers: 1,
  outputDir: './test-results/playwright',
  reporter: 'list',
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1280, height: 900 },
        trace: process.env.UI_PERF_TRACE === '1' ? 'on' : 'off',
      },
    },
  ],
  use: {
    baseURL: 'http://127.0.0.1:4173',
    actionTimeout: 10000,
    storageState: {
      cookies: [],
      origins: [
        {
          origin: 'http://127.0.0.1:4173',
          localStorage: [{ name: 'fallout_changelog_last_seen', value: '999.0.0' }],
        },
      ],
    },
  },
  webServer: {
    command: 'pnpm run preview -- --host 127.0.0.1 --port 4173 --strictPort',
    url: 'http://127.0.0.1:4173',
    reuseExistingServer: false,
    timeout: 30000,
  },
})
