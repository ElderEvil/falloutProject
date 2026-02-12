import { test, expect } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))
const authFile = join(__dirname, '../.auth/user.json')

test.describe('Authentication', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login')
  })

  test('should display login form', async ({ page }) => {
    await expect(page).toHaveTitle(/Login|Authenticate|Sign/i)

    await expect(page.getByLabel(/email/i)).toBeVisible()
    await expect(page.getByLabel(/password/i)).toBeVisible()
    await expect(page.getByRole('button', { name: /sign.?in|login/i })).toBeVisible()
  })

  test('should show validation errors for empty fields', async ({ page }) => {
    const submitButton = page.getByRole('button', { name: /sign.?in|login/i })

    await submitButton.click()

    await expect(page.getByText(/required|empty|invalid/i)).toBeVisible()
  })

  test('should show error for invalid credentials', async ({ page }) => {
    await page.getByLabel(/email/i).fill('invalid@example.com')
    await page.getByLabel(/password/i).fill('wrongpassword')
    await page.getByRole('button', { name: /sign.?in|login/i }).click()

    await expect(page.getByText(/invalid|unauthorized|wrong/i)).toBeVisible()
  })

  test('should redirect to login when accessing protected route without auth', async ({ page }) => {
    await page.goto('/vault')
    await page.waitForURL(/\/login/i, { timeout: 5000 })
  })

  test('should remember me functionality', async ({ page }) => {
    const rememberMeCheckbox = page.getByLabel(/remember.?me|keep.?me/i)

    if (await rememberMeCheckbox.count() > 0) {
      await rememberMeCheckbox.check()
      await expect(rememberMeCheckbox).toBeChecked()
    }
  })
})

test.describe('Authentication - Logged In', () => {
  test.use({ storageState: authFile })

  test('should access dashboard when authenticated', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    await expect(page.getByRole('navigation')).toBeVisible()
  })

  test('should show user menu when authenticated', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    const userMenu = page.getByRole('button', { name: /user|profile|account/i })
    if (await userMenu.count() > 0) {
      await userMenu.click()
      await expect(page.getByText(/logout|sign.?out/i)).toBeVisible()
    }
  })
})
