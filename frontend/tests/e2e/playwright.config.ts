import { defineConfig, devices } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  testDir: join(__dirname, 'specs'),
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',

  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },

  projects: [
    {
      name: 'setup',
      testDir: __dirname,
      testMatch: /support\/e2e\.setup\.ts/,
    },
    ...(process.env.CI
      ? [
          {
            name: 'chromium',
            use: {
              ...devices['Desktop Chrome'],
              storageState: join(__dirname, '.auth/user.json'),
            },
            dependencies: ['setup'],
          },
        ]
      : [
          {
            name: 'chromium',
            use: {
              ...devices['Desktop Chrome'],
              storageState: join(__dirname, '.auth/user.json'),
            },
            dependencies: ['setup'],
          },
          {
            name: 'firefox',
            use: {
              ...devices['Desktop Firefox'],
              storageState: join(__dirname, '.auth/user.json'),
            },
            dependencies: ['setup'],
          },
          {
            name: 'webkit',
            use: {
              ...devices['Desktop Safari'],
              storageState: join(__dirname, '.auth/user.json'),
            },
            dependencies: ['setup'],
          },
        ]),
  ],

  webServer: {
    command: 'pnpm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 120000,
  },

  expect: {
    timeout: 10000,
    toHaveScreenshot: {
      maxDiffPixels: 100,
    },
  },

  timeout: 30000,
})
