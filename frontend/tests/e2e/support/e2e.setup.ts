import { test as setup, expect } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))
const authFile = join(__dirname, '../.auth/user.json')

setup('authenticate', async ({ page }) => {
  await page.goto('/login')
  await expect(page).toHaveTitle(/Login|Authenticate|Sign/i)

  const emailInput = page.getByLabel(/email/i)
  const passwordInput = page.getByLabel(/password/i)
  const submitButton = page.getByRole('button', { name: /sign.?in|login|enter/i })

  if (await emailInput.count() === 0) {
    throw new Error('Login form not found — email input is missing. Cannot create authenticated storage state.')
  }

  if (await passwordInput.count() === 0) {
    throw new Error('Login form not found — password input is missing. Cannot create authenticated storage state.')
  }

  await emailInput.fill(process.env.E2E_USER_EMAIL || 'admin@vault.shelter')
  await passwordInput.fill(process.env.E2E_USER_PASSWORD || 'admin123')
  await submitButton.click()

  await page.waitForURL(/\/(?:vault|dashboard|home)?$/, { timeout: 10000 })

  await page.context().storageState({ path: authFile })
})
