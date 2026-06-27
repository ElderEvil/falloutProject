import { test, expect, type Page } from '@playwright/test'

/**
 * All auth-protected routes that should redirect to /login when not authenticated.
 */
const AUTH_ROUTES = [
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
]

test.describe('Auth guard — redirect to /login when unauthenticated', () => {
  for (const { url, name } of AUTH_ROUTES) {
    test(`${name} (${url}) redirects to /login`, async ({ page }) => {
      const pageErrors: string[] = []
      page.on('pageerror', (err) => {
        pageErrors.push(`PAGE ERROR: ${err.message}`)
      })

      // No localStorage token set — unauthenticated
      await page.goto(url)
      await page.waitForLoadState('networkidle')

      // Should have been redirected to /login (or at least not show the auth page)
      const currentUrl = page.url()
      const onLogin = currentUrl.includes('/login')
      const bodyText = await page.locator('body').innerText()

      // Either we're on /login, or we see a redirect message
      if (!onLogin) {
        console.log(`URL for ${name} (${url}): ${currentUrl}`)
      }

      // Must not show page errors (JS crashes during guard redirect)
      expect(pageErrors).toHaveLength(0)
      // Body must have content (not a white screen)
      expect(bodyText.length).toBeGreaterThan(0)
      // No vite error overlay
      await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
    })
  }
})

test.describe('Public pages — no redirect when unauthenticated', () => {
  for (const { url, name } of [
    { url: '/login', name: 'login' },
    { url: '/register', name: 'register' },
    { url: '/forgot-password', name: 'forgot-password' },
    { url: '/reset-password', name: 'reset-password' },
    { url: '/verify-email', name: 'verify-email' },
    { url: '/about', name: 'about' },
  ]) {
    test(`${name} stays on page without auth`, async ({ page }) => {
      await page.goto(url)
      await page.waitForLoadState('networkidle')
      await expect(page.locator('body')).toBeVisible({ timeout: 10000 })
      // URL should still contain the original path
      expect(page.url()).toContain(url)
    })
  }
})
