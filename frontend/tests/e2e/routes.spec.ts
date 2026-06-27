import { test, expect, type Page } from '@playwright/test'

/**
 * Navigate to a public page (no auth required).
 * Verifies 0 console errors, 0 page errors, body renders, no vite overlay.
 */
async function checkPublicPage(page: Page, url: string) {
  const consoleErrors: string[] = []
  const pageErrors: string[] = []

  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text())
  })
  page.on('pageerror', (err) => {
    pageErrors.push(`PAGE ERROR: ${err.message}`)
  })

  await page.goto(url)
  await page.waitForLoadState('networkidle')
  await expect(page.locator('body')).toBeVisible({ timeout: 10000 })
  await expect(page.locator('#vite-error-overlay')).toHaveCount(0)

  if (pageErrors.length > 0) {
    console.log('Page errors:', JSON.stringify(pageErrors, null, 2))
  }
  if (consoleErrors.length > 0) {
    console.log('Console errors:', JSON.stringify(consoleErrors, null, 2))
  }

  expect(pageErrors).toHaveLength(0)
  expect(consoleErrors).toHaveLength(0)
}

/**
 * True JS crash errors (TypeError, ReferenceError, SyntaxError, etc.)
 * These are always real bugs regardless of auth state.
 */
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
 * Navigate to an auth page with a fake token.
 * Tolerates 403 console errors and page errors from API calls (expected with fake tokens),
 * but checks for NO real JS crashes (TypeError, ReferenceError, etc.) and NO vite overlay.
 */
async function checkAuthPage(page: Page, url: string) {
  const allPageErrors: string[] = []
  const realJSErrors: string[] = []

  page.on('pageerror', (err) => {
    const msg = `PAGE ERROR: ${err.message}`
    allPageErrors.push(msg)
    if (isRealJsError(msg)) {
      realJSErrors.push(msg)
    }
  })

  // Login first to set localStorage on the origin
  await page.goto('/login')
  await page.evaluate(() => {
    localStorage.setItem('token', 'test-token-12345')
    localStorage.setItem(
      'user',
      JSON.stringify({
        id: 'test-user-id',
        email: 'test@example.com',
        is_active: true,
        is_superuser: true,
      })
    )
  })
  await page.goto(url)
  await page.waitForLoadState('networkidle')
  await expect(page.locator('body')).toBeVisible({ timeout: 10000 })
  await expect(page.locator('#vite-error-overlay')).toHaveCount(0)

  if (allPageErrors.length > 0) {
    console.log(`Page errors on ${url}:`, JSON.stringify(allPageErrors, null, 2))
  }
  if (realJSErrors.length > 0) {
    console.log(`REAL JS ERRORS on ${url}:`, JSON.stringify(realJSErrors, null, 2))
  }

  expect(realJSErrors).toHaveLength(0)
}

test.describe('Public page coverage — 0 console errors expected', () => {
  for (const { url, name } of [
    { url: '/login', name: 'login' },
    { url: '/register', name: 'register' },
    { url: '/forgot-password', name: 'forgot-password' },
    { url: '/reset-password', name: 'reset-password' },
    { url: '/verify-email', name: 'verify-email' },
    { url: '/about', name: 'about' },
  ]) {
    test(`${name} — renders without errors`, async ({ page }) => {
      await checkPublicPage(page, url)
    })
  }
})

test.describe('Auth page coverage — no page errors (403 console tolerated)', () => {
  const authPages: { url: string; name: string }[] = [
    { url: '/', name: 'home' },
    { url: '/vault/fake-id', name: 'vault' },
    { url: '/vault/fake-id/happiness', name: 'happiness' },
    { url: '/vault/fake-id/storage', name: 'storage' },
    { url: '/vault/fake-id/dwellers', name: 'dwellers' },
    { url: '/vault/fake-id/dwellers/test-id', name: 'dweller-detail' },
    { url: '/vault/fake-id/dwellers/graveyard', name: 'graveyard' },
    { url: '/vault/fake-id/exploration', name: 'exploration' },
    { url: '/vault/fake-id/exploration/test-id', name: 'exploration-detail' },
    { url: '/vault/fake-id/training', name: 'training' },
    { url: '/vault/fake-id/quests', name: 'quests' },
    { url: '/vault/fake-id/quests/test-id', name: 'quest-detail' },
    { url: '/vault/fake-id/objectives', name: 'objectives' },
    { url: '/vault/fake-id/radio', name: 'radio' },
    { url: '/vault/fake-id/relationships', name: 'relationships' },
    { url: '/profile', name: 'profile' },
    { url: '/settings', name: 'settings' },
    { url: '/preferences', name: 'preferences' },
    { url: '/changelog', name: 'changelog' },
    { url: '/nuxt-ui-poc', name: 'nuxt-ui-poc' },
    { url: '/vault/fake-id/storage', name: 'storage-repeat' },
  ]

  for (const { url, name } of authPages) {
    test(`${name} — no page errors`, async ({ page }) => {
      await checkAuthPage(page, url)
    })
  }
})

test.describe('Edge case auth pages — no page errors', () => {
  test('empty vault id — no page error', async ({ page }) => {
    await checkAuthPage(page, '/vault/')
  })

  test('unknown vault sub-route — no page error', async ({ page }) => {
    await checkAuthPage(page, '/vault/fake-id/nonexistent')
  })
})
