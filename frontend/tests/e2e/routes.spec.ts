import { expect, test, type Page } from '@playwright/test'
import { open, seedSession } from './support/session'
import { collectErrors } from './support/telemetry'

/**
 * Navigate to a public page (no auth required).
 * Verifies 0 console errors, 0 page errors, body renders, no vite overlay.
 */
async function checkPublicPage(page: Page, url: string) {
  const errors = collectErrors(page)

  await open(page, url)
  await expect(page.locator('body')).toBeVisible({ timeout: 10000 })
  await expect(page.locator('#vite-error-overlay')).toHaveCount(0)

  if (errors.all.length > 0) console.log(`Errors on ${url}:`, JSON.stringify(errors.all, null, 2))
  expect(errors.page).toHaveLength(0)
  expect(errors.console).toHaveLength(0)
}

/**
 * Navigate to an auth page with a fake token.
 * Tolerates 403 console errors and page errors from API calls (expected with fake tokens),
 * but checks for NO real JS crashes (TypeError, ReferenceError, etc.) and NO vite overlay.
 */
async function checkAuthPage(page: Page, url: string) {
  const errors = collectErrors(page)

  // Login first to set localStorage on the origin
  await page.goto('/login')
  await seedSession(page)
  await open(page, url)
  await expect(page.locator('body')).toBeVisible({ timeout: 10000 })
  await expect(page.locator('#vite-error-overlay')).toHaveCount(0)

  if (errors.all.length > 0) {
    console.log(`Errors on ${url}:`, JSON.stringify(errors.all, null, 2))
  }
  expect(errors.real).toHaveLength(0)
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
    { url: '/vault/fake-id/quests?claimQuest=test-id', name: 'quest-reward-claim' },
    { url: '/vault/fake-id/objectives', name: 'objectives' },
    { url: '/vault/fake-id/radio', name: 'radio' },
    { url: '/vault/fake-id/relationships', name: 'relationships' },
    { url: '/profile', name: 'profile' },
    { url: '/settings', name: 'settings' },
    { url: '/preferences', name: 'preferences' },
    { url: '/changelog', name: 'changelog' },
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
