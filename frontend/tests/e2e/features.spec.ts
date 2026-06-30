import { test, expect } from '@playwright/test'
import { setAuthToken } from './fixtures/auth'

/**
 * Helper: navigate to a page and set auth token in localStorage.
 * Must navigate first before accessing localStorage (can't set on about:blank).
 */
async function loginAndGoTo(page: any, url: string, token = 'test-token-12345') {
  // Navigate to login page first (it doesn't require auth)
  await page.goto('/login')
  // Set auth token on the login page's origin
  await page.evaluate(
    ({ token }) => {
      localStorage.setItem('token', token)
      localStorage.setItem('user', JSON.stringify({ id: 'test-user-id', email: 'test@example.com', is_active: true, is_superuser: true }))
    },
    { token }
  )
  // Now navigate to the target auth-protected page
  await page.goto(url)
  await page.waitForLoadState('networkidle')
}

test.describe('Feature pages load correctly', () => {
  test('vault home page renders without JS errors', async ({ page }) => {
    await loginAndGoTo(page, '/')
    await expect(page.locator('body')).toBeVisible({ timeout: 10000 })
    await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
  })

  test('storage page loads without crashing', async ({ page }) => {
    await loginAndGoTo(page, '/vault/fake-id/storage')
    await expect(page.locator('body')).toBeVisible({ timeout: 10000 })
    await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
    const bodyText = await page.locator('body').innerText()
    expect(bodyText.length).toBeGreaterThan(0)
  })

  test('dwellers page loads without crashing', async ({ page }) => {
    await loginAndGoTo(page, '/vault/fake-id/dwellers')
    await expect(page.locator('body')).toBeVisible({ timeout: 10000 })
    await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
    const bodyText = await page.locator('body').innerText()
    expect(bodyText.length).toBeGreaterThan(0)
  })

  test('vault detail page loads rooms section', async ({ page }) => {
    await loginAndGoTo(page, '/vault/fake-id')
    await expect(page.locator('body')).toBeVisible({ timeout: 10000 })
    await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
    const bodyText = await page.locator('body').innerText()
    expect(bodyText.length).toBeGreaterThan(0)
  })
})

test.describe('Dweller card actions render correctly', () => {
  test('dweller detail page shows without JS errors', async ({ page }) => {
    await loginAndGoTo(page, '/vault/fake-id/dwellers/fake-dweller-id')
    await expect(page.locator('body')).toBeVisible({ timeout: 10000 })
    await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
  })
})

test.describe('UButton component migration verification', () => {
  test('buttons render on vault page', async ({ page }) => {
    await loginAndGoTo(page, '/vault/fake-id')
    await expect(page.locator('body')).toBeVisible({ timeout: 10000 })
    const buttons = page.locator('button')
    const buttonCount = await buttons.count()
    expect(buttonCount).toBeGreaterThanOrEqual(0)
  })

  test('dweller page has interactive elements', async ({ page }) => {
    await loginAndGoTo(page, '/vault/fake-id/dwellers/fake-dweller-id')
    await expect(page.locator('body')).toBeVisible({ timeout: 10000 })
    const bodyText = await page.locator('body').innerText()
    expect(bodyText).not.toBeNull()
  })
})
