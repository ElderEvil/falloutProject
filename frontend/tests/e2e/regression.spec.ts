import { test, expect, type Page } from '@playwright/test'

const TEST_TOKEN = 'test-token-12345'

function isRealJsError(msg: string): boolean {
  const networkErrors = [
    'Request failed with status code',
    'Failed to load resource',
    'Network Error',
    'timeout of',
    'canceled',
  ]
  return !networkErrors.some((prefix) => msg.includes(prefix))
}

/**
 * Navigate to a page and inject auth token to bypass login.
 * Must navigate to the app origin first before setting localStorage.
 */
async function loginAndGo(page: Page, url: string) {
  await page.goto('/login')
  await page.evaluate((token) => {
    localStorage.setItem('token', token)
    localStorage.setItem(
      'user',
      JSON.stringify({ id: 'test-user-id', email: 'test@example.com', is_active: true, is_superuser: true })
    )
  }, TEST_TOKEN)
  await page.goto(url)
  await page.waitForLoadState('networkidle')
}

test.describe('Console error audit', () => {
  const allErrors: string[] = []

  test.beforeEach(async ({ page }) => {
    allErrors.length = 0
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        allErrors.push(msg.text())
      }
    })
    page.on('pageerror', (err) => {
      allErrors.push(`PAGE ERROR: ${err.message}`)
    })
  })

  test.afterEach(async () => {
    const realErrors = allErrors.filter((e) => isRealJsError(e))
    if (realErrors.length > 0) {
      console.log('Real JS errors:', JSON.stringify(realErrors, null, 2))
    }
    expect(realErrors).toHaveLength(0)
  })

  test('home page - no real JS errors', async ({ page }) => {
    await loginAndGo(page, '/')
    await expect(page.locator('body')).toBeVisible()
    await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
  })

  test('login page - no console errors (no auth needed)', async ({ page }) => {
    await page.goto('/login')
    await page.waitForLoadState('networkidle')
    await expect(page.locator('body')).toBeVisible()
  })

  test('vault page - no real JS errors', async ({ page }) => {
    await loginAndGo(page, '/vault/fake-id')
    await expect(page.locator('body')).toBeVisible()
  })

  test('storage page - no real JS errors', async ({ page }) => {
    await loginAndGo(page, '/vault/fake-id/storage')
    await expect(page.locator('body')).toBeVisible()
  })

  test('dwellers page - no real JS errors', async ({ page }) => {
    await loginAndGo(page, '/vault/fake-id/dwellers')
    await expect(page.locator('body')).toBeVisible()
  })

  test('dweller detail page - no real JS errors', async ({ page }) => {
    await loginAndGo(page, '/vault/fake-id/dwellers/fake-id')
    await expect(page.locator('body')).toBeVisible()
  })

  test('register page - no console errors', async ({ page }) => {
    await page.goto('/register')
    await page.waitForLoadState('networkidle')
    await expect(page.locator('body')).toBeVisible()
  })

  test('settings page - no real JS errors', async ({ page }) => {
    await loginAndGo(page, '/settings')
    await expect(page.locator('body')).toBeVisible()
  })
})

test.describe('Navigation smoke test', () => {
  test.beforeEach(async ({ page }) => {
    await loginAndGo(page, '/')
  })

  test('can navigate between major sections', async ({ page }) => {
    // Navigate to vault
    await page.goto('/vault/fake-id')
    await page.waitForLoadState('networkidle')
    await expect(page.locator('body')).toBeVisible()

    // Navigate to dwellers
    await page.goto('/vault/fake-id/dwellers')
    await page.waitForLoadState('networkidle')
    await expect(page.locator('body')).toBeVisible()

    // Navigate to storage
    await page.goto('/vault/fake-id/storage')
    await page.waitForLoadState('networkidle')
    await expect(page.locator('body')).toBeVisible()

    // Navigate back to home
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await expect(page.locator('body')).toBeVisible()
  })
})

test.describe('UI component rendering', () => {
  test('UButton variants exist on login page', async ({ page }) => {
    await page.goto('/login')
    await page.waitForLoadState('networkidle')
    // Login page should have buttons (submit, register link, etc.)
    const buttons = page.locator('button')
    const count = await buttons.count()
    expect(count).toBeGreaterThanOrEqual(1)
  })

  test('register form has input fields', async ({ page }) => {
    await page.goto('/register')
    await page.waitForLoadState('networkidle')
    const inputs = page.locator('input')
    const count = await inputs.count()
    expect(count).toBeGreaterThanOrEqual(2)
  })

  test('app does not render NuxtUiPocView as default', async ({ page }) => {
    await page.goto('/nuxt-ui-poc')
    await page.waitForLoadState('networkidle')
    await expect(page.locator('body')).toBeVisible()
  })
})

test.describe('Error handling / edge cases', () => {
  test('unknown route shows something (no full crash)', async ({ page }) => {
    await loginAndGo(page, '/this-route-does-not-exist-at-all')
    await expect(page.locator('body')).toBeVisible({ timeout: 10000 })
    // Should show some kind of content (error page or redirect) — not a white screen
    const bodyText = await page.locator('body').innerText()
    expect(bodyText.length).toBeGreaterThan(0)
    await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
  })

  test('vault page with empty id does not crash', async ({ page }) => {
    await loginAndGo(page, '/vault/')
    await expect(page.locator('body')).toBeVisible({ timeout: 10000 })
    await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
  })

  test('back-to-back rapid navigation does not cause errors', async ({ page }) => {
    await loginAndGo(page, '/login')
    const urls = ['/', '/vault/fake-id', '/vault/fake-id/dwellers', '/vault/fake-id/storage', '/settings', '/login']
    for (const url of urls) {
      await page.goto(url)
      await page.waitForTimeout(200)
    }
    await expect(page.locator('body')).toBeVisible()
    await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
  })
})
