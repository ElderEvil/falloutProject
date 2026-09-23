import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  retries: 1,
  workers: 2,
  reporter: [['html', { open: 'never' }], ['list']],
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1280, height: 720 },
      },
    },
  ],
  webServer: [
    {
      command: 'cd ../backend && uv run fastapi dev main.py',
      url: 'http://localhost:8000/healthcheck',
      reuseExistingServer: true,
    },
    {
      command: 'pnpm run dev',
      port: 5173,
      reuseExistingServer: true,
    },
  ],
  use: {
    baseURL: 'http://localhost:5173',
    // Seed the version-seen key so the first-run "What's New" changelog modal never
    // mounts: it otherwise races the app's version-detection fetch and intermittently
    // intercepts clicks, making whichever spec clicks first flaky.
    storageState: {
      cookies: [],
      origins: [
        {
          origin: 'http://localhost:5173',
          localStorage: [{ name: 'fallout_changelog_last_seen', value: '999.0.0' }],
        },
      ],
    },
  },
})
