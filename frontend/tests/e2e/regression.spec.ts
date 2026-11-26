import { test, expect } from '@playwright/test'
import { open, openAs } from './support/session'
import { collectErrors, isRealJsError, type ErrorLog } from './support/telemetry'

test.describe('Console error audit', () => {
  let errors: ErrorLog

  test.beforeEach(async ({ page }) => {
    errors = collectErrors(page)
  })

  test.afterEach(async () => {
    const realErrors = errors.all.filter((message) => isRealJsError(message))
    if (realErrors.length > 0) {
      console.log('Real JS errors:', JSON.stringify(realErrors, null, 2))
    }
    expect(realErrors).toHaveLength(0)
  })

  test('home page - no real JS errors', async ({ page }) => {
    await openAs(page, '/')
    await expect(page.locator('body')).toBeVisible()
    await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
  })

  test('login page - no console errors (no auth needed)', async ({ page }) => {
    await open(page, '/login')
    await expect(page.locator('body')).toBeVisible()
  })

  test('vault page - no real JS errors', async ({ page }) => {
    await openAs(page, '/vault/fake-id')
    await expect(page.locator('body')).toBeVisible()
  })

  test('storage page - no real JS errors', async ({ page }) => {
    await openAs(page, '/vault/fake-id/storage')
    await expect(page.locator('body')).toBeVisible()
  })

  test('dwellers page - no real JS errors', async ({ page }) => {
    await openAs(page, '/vault/fake-id/dwellers')
    await expect(page.locator('body')).toBeVisible()
  })

  test('dweller detail page - no real JS errors', async ({ page }) => {
    await openAs(page, '/vault/fake-id/dwellers/fake-id')
    await expect(page.locator('body')).toBeVisible()
  })

  test('register page - no console errors', async ({ page }) => {
    await open(page, '/register')
    await expect(page.locator('body')).toBeVisible()
  })

  test('settings page - no real JS errors', async ({ page }) => {
    await openAs(page, '/settings')
    await expect(page.locator('body')).toBeVisible()
  })
})

test.describe('Navigation smoke test', () => {
  test.beforeEach(async ({ page }) => {
    await openAs(page, '/')
  })

  test('can navigate between major sections', async ({ page }) => {
    // Navigate to vault
    await open(page, '/vault/fake-id')
    await expect(page.locator('body')).toBeVisible()

    // Navigate to dwellers
    await open(page, '/vault/fake-id/dwellers')
    await expect(page.locator('body')).toBeVisible()

    // Navigate to storage
    await open(page, '/vault/fake-id/storage')
    await expect(page.locator('body')).toBeVisible()

    // Navigate back to home
    await open(page, '/')
    await expect(page.locator('body')).toBeVisible()
  })
})

test.describe('UI component rendering', () => {
  test('UButton variants exist on login page', async ({ page }) => {
    await open(page, '/login')
    // Login page should have buttons (submit, register link, etc.)
    const buttons = page.locator('button')
    const count = await buttons.count()
    expect(count).toBeGreaterThanOrEqual(1)
  })

  test('register form has input fields', async ({ page }) => {
    await open(page, '/register')
    const inputs = page.locator('input')
    const count = await inputs.count()
    expect(count).toBeGreaterThanOrEqual(2)
  })
})

test.describe('Error handling / edge cases', () => {
  test('unknown route shows something (no full crash)', async ({ page }) => {
    await openAs(page, '/this-route-does-not-exist-at-all')
    await expect(page.locator('body')).toBeVisible({ timeout: 10000 })
    // Should show some kind of content (error page or redirect) — not a white screen
    const bodyText = await page.locator('body').innerText()
    expect(bodyText.length).toBeGreaterThan(0)
    await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
  })

  test('vault page with empty id does not crash', async ({ page }) => {
    await openAs(page, '/vault/')
    await expect(page.locator('body')).toBeVisible({ timeout: 10000 })
    await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
  })

  test('back-to-back rapid navigation does not cause errors', async ({ page }) => {
    await openAs(page, '/login')
    const urls = [
      '/',
      '/vault/fake-id',
      '/vault/fake-id/dwellers',
      '/vault/fake-id/storage',
      '/settings',
      '/login',
    ]
    for (const url of urls) {
      await page.goto(url)
      await page.waitForTimeout(200)
    }
    await expect(page.locator('body')).toBeVisible()
    await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
  })
})
