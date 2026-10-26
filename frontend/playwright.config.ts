import { defineConfig, devices } from '@playwright/test'

// The visual-baseline specs (`crt-baselines`, `ui-catalog`) mock every backend call
// they make, so CI runs them against the Vite dev server alone: PW_SKIP_BACKEND=1
// drops the FastAPI webServer and starts Vite directly. `pnpm exec vp dev` skips
// `types:generate`, which needs a live backend — the generated client is committed.
const skipBackend = process.env.PW_SKIP_BACKEND === '1'

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
    {
      name: 'firefox-scenes',
      testMatch: 'wasteland-scenes.spec.ts',
      use: {
        ...devices['Desktop Firefox'],
        viewport: { width: 1280, height: 720 },
      },
    },
    {
      // First-frame sizing regressions only reproduced in Firefox (#1187), so
      // the sizing specs get a focused second browser instead of doubling every
      // baseline run.
      name: 'firefox-sizing',
      testMatch: ['room-preview.spec.ts', 'sizing-contract.spec.ts'],
      use: {
        ...devices['Desktop Firefox'],
        viewport: { width: 1280, height: 720 },
      },
    },
  ],
  webServer: [
    ...(skipBackend
      ? []
      : [
          {
            command: 'cd ../backend && uv run fastapi dev main.py',
            url: 'http://localhost:8000/healthcheck',
            reuseExistingServer: true,
          },
        ]),
    {
      command: skipBackend ? 'pnpm exec vp dev' : 'pnpm run dev',
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
