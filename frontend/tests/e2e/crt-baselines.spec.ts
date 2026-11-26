import { test, expect, type Page } from '@playwright/test'
import { json, mockApi as mockRoutes, sse } from './support/api'
import { AUTH_USER, deathStatistics, profile, VAULT } from './support/data'
import { openAs } from './support/session'

// Pixel baselines for the CRT entry routes (#748). #747 unified the scanline
// overlay into one layout-level element, so every route must render exactly one
// full-opacity .scanlines overlay; these specs pin that contract and the panels
// behind it. All backend traffic is mocked so the output depends only on the
// frontend markup and styles.
test.use({
  reducedMotion: 'reduce',
  locale: 'en-US',
  timezoneId: 'UTC',
  viewport: { width: 1280, height: 900 },
})

const TOKEN = 'deterministic-e2e-token'
const RESET_TOKEN = 'deterministic-reset-token'

// The frontend reads quota fields flattened (models/aiUsage.ts); mocking the
// backend's nested quota object would hide the quota panel instead of rendering it.
const AI_USAGE = {
  all_time: { prompt_tokens: 820000, completion_tokens: 430000, total_tokens: 1250000 },
  current_month: { prompt_tokens: 120000, completion_tokens: 60000, total_tokens: 180000 },
  month: '2026-02',
  quota_limit: 500000,
  quota_used: 180000,
  quota_remaining: 320000,
  quota_percentage: 36,
  quota_warning: false,
  quota_exceeded: false,
  reset_date: '2026-03-01',
  by_operation: [
    {
      operation: 'chat_with_dweller',
      prompt_tokens: 90000,
      completion_tokens: 45000,
      total_tokens: 135000,
      count: 34,
      is_operational: false,
    },
    {
      operation: 'generate_backstory',
      prompt_tokens: 30000,
      completion_tokens: 15000,
      total_tokens: 45000,
      count: 3,
      is_operational: false,
    },
  ],
  chat_heavy: false,
}

const PROFILE = profile({
  bio: 'Overseer of Vault 42, keeping the lights on since the bombs fell.',
  preferences: null,
})

// An unhandled request is a hole in the mock, so the CRT baseline fails loudly.
const mockApi = (page: Page) =>
  mockRoutes(
    page,
    [
      { path: '/api/v1/users/me/profile', reply: json(PROFILE) },
      { path: '/api/v1/users/me/profile/statistics', reply: json(deathStatistics()) },
      { path: '/api/v1/users/me/profile/ai-usage', reply: json(AI_USAGE) },
      { path: '/api/v1/users/me', reply: json(AUTH_USER) },
      { path: '/api/v1/auth/oauth/providers', reply: json({ google: false, github: false }) },
      { path: '/api/v1/vaults/my', reply: json([VAULT]) },
      { path: '/api/v1/notifications/unread-count', reply: json({ count: 0 }) },
      { path: '/api/v1/notifications/', reply: json([]) },
      { prefix: '/api/v1/stream/', reply: sse() },
    ],
    { fallback: 'throw' }
  )

// Regression guard for #747: one canonical overlay, full opacity, canonical
// gradient — a re-added per-view overlay or an `opacity-*` on this element fails here.
async function expectCanonicalChrome(page: Page, superuser = false) {
  // Iconify renders an empty <svg class="iconify"> until its icon body is fetched,
  // so without this wait a fresh page can be captured icon-less (CI vs local drift).
  await expect(page.locator('svg.iconify path').first()).toBeVisible({ timeout: 20000 })
  if (superuser) {
    const launcher = page.getByRole('button', { name: /open the admin terminal/i })
    await expect(launcher).toBeVisible()
    await expect(launcher.locator('svg path').first()).toBeVisible()
  }

  const overlay = page.locator('.scanlines')
  await expect(overlay).toHaveCount(1)
  await expect(overlay).toHaveAttribute('aria-hidden', 'true')
  await expect(overlay).toHaveCSS('opacity', '1')
  await expect(overlay).toHaveCSS('position', 'fixed')
  await expect(overlay).toHaveCSS('background-image', /repeating-linear-gradient/)
}

test.describe('CRT baselines — entry routes', () => {
  test('home', async ({ page }) => {
    await mockApi(page)
    await openAs(page, '/', { token: TOKEN, user: AUTH_USER })
    await expect(page.getByRole('heading', { name: 'Your Vaults' })).toBeVisible({ timeout: 10000 })

    await expectCanonicalChrome(page, true)
    await expect(page).toHaveScreenshot('home.png', { animations: 'disabled', timeout: 20000 })
  })

  test('login', async ({ page }) => {
    await mockApi(page)
    await page.goto('/login')
    await expect(page.locator('#login-username')).toBeVisible({ timeout: 10000 })

    await expectCanonicalChrome(page)
    await expect(page).toHaveScreenshot('login.png', {
      animations: 'disabled',
      mask: [page.locator('.system-messages p').first()],
      timeout: 20000,
    })
  })

  test('register', async ({ page }) => {
    await mockApi(page)
    await page.goto('/register')
    await expect(page.locator('#register-username')).toBeVisible({ timeout: 10000 })

    await expectCanonicalChrome(page)
    await expect(page).toHaveScreenshot('register.png', {
      animations: 'disabled',
      mask: [page.locator('.system-messages p').first()],
      timeout: 20000,
    })
  })

  test('password reset', async ({ page }) => {
    await page.goto(`/reset-password?token=${RESET_TOKEN}`)
    await expect(page.locator('#reset-new-password')).toBeVisible({ timeout: 10000 })
    await expect(page.locator('.error-message')).toHaveCount(0)

    await expectCanonicalChrome(page)
    await expect(page).toHaveScreenshot('reset-password.png', {
      animations: 'disabled',
      timeout: 20000,
    })
  })

  test('profile', async ({ page }) => {
    await mockApi(page)
    await openAs(page, '/profile', { token: TOKEN, user: AUTH_USER })
    await expect(page.getByRole('heading', { name: 'User Profile' })).toBeVisible({
      timeout: 10000,
    })
    await expect(page.getByRole('tab', { name: 'Dossier' })).toBeVisible()
    await expect(page.getByRole('tab', { name: 'AI Settings' })).toHaveCount(0)
    const adminLinks = page.getByRole('navigation', { name: 'Administration', exact: true })
    await expect(
      adminLinks.getByRole('link', { name: 'AI settings', exact: true })
    ).toHaveAttribute('href', '/admin/ai-settings')
    await expect(adminLinks.getByRole('link', { name: 'Admin console' })).toHaveAttribute(
      'href',
      /\/admin\/$/
    )
    await expect(page.getByRole('button', { name: /View activity and AI usage/ })).toHaveCount(0)

    await expectCanonicalChrome(page, true)
    await expect(page).toHaveScreenshot('profile-dossier.png', {
      animations: 'disabled',
      timeout: 20000,
    })

    await page.getByRole('tab', { name: 'Vault Analytics' }).click()
    await expect(page.locator('section[aria-label="Vault analytics"]')).toBeVisible()

    // Grow the viewport to the tab's full height so the fixed chrome (sidebar,
    // scanline overlay) covers the capture instead of ending at the fold.
    const analyticsHeight = await page.evaluate(() => document.documentElement.scrollHeight)
    await page.setViewportSize({ width: 1280, height: analyticsHeight })
    await expect(page).toHaveScreenshot('profile-analytics.png', {
      animations: 'disabled',
      timeout: 20000,
    })
  })
})

test('CSS flicker obeys its preference and reduced motion, including teleported content', async ({
  page,
}) => {
  await mockApi(page)
  await page.emulateMedia({ reducedMotion: 'no-preference' })
  await page.goto('/login')
  await page.evaluate(() => {
    for (const cls of ['flicker', 'flicker-random', 'flicker-slow']) {
      const probe = document.createElement('div')
      probe.className = cls
      probe.dataset.testid = cls
      document.body.append(probe)
    }
  })
  for (const cls of ['flicker', 'flicker-random', 'flicker-slow']) {
    await expect(page.getByTestId(cls)).toHaveCSS('animation-name', 'none')
  }
  await page.evaluate(() => {
    localStorage.setItem('visual-effects:flickering', 'true')
    window.dispatchEvent(
      new StorageEvent('storage', {
        key: 'visual-effects:flickering',
        newValue: 'true',
        storageArea: localStorage,
      })
    )
  })
  for (const cls of ['flicker', 'flicker-random', 'flicker-slow']) {
    await expect(page.getByTestId(cls)).toHaveCSS('animation-name', 'flicker')
  }
  await page.emulateMedia({ reducedMotion: 'reduce' })
  for (const cls of ['flicker', 'flicker-random', 'flicker-slow']) {
    await expect(page.getByTestId(cls)).toHaveCSS('animation-name', 'none')
  }
})

test('legacy auth views obey the disabled flicker preference', async ({ page }) => {
  await mockApi(page)
  await page.emulateMedia({ reducedMotion: 'no-preference' })
  for (const path of [
    '/forgot-password',
    `/reset-password?token=${RESET_TOKEN}`,
    '/verify-email',
  ]) {
    await page.goto(path)
    const panel = page.locator('#app .crt-container, #app .terminal-window').first()
    await expect(panel).toBeVisible()
    await expect(panel).toHaveCSS('animation-name', 'none')
  }
})

for (const width of [390, 1280]) {
  test(`Preferences tabs support links and keyboard navigation at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await mockApi(page)
    await openAs(page, '/preferences?tab=sound', { token: TOKEN, user: AUTH_USER })

    const tabs = page.getByRole('tablist', { name: 'Preference categories' })
    for (const name of ['Appearance', 'Sound', 'Notifications', 'Gameplay']) {
      const tab = tabs.getByRole('tab', { name, exact: true })
      await expect(tab).toBeVisible()
      const box = await tab.boundingBox()
      expect(box!.x).toBeGreaterThanOrEqual(0)
      expect(box!.x + box!.width).toBeLessThanOrEqual(width)
    }
    await expect(page.getByRole('tabpanel')).toContainText('Sound Enabled')
    await expect(page.getByRole('slider')).toHaveCount(4)
    for (const slider of await page.getByRole('slider').all()) {
      await expect(slider).toHaveAttribute('data-disabled', '')
      await expect(slider).not.toHaveAttribute('tabindex', '0')
    }

    await tabs.getByRole('tab', { name: 'Sound', exact: true }).focus()
    await page.keyboard.press('ArrowRight')
    await expect(page).toHaveURL(/tab=notifications/)
    await expect(page.getByRole('tabpanel')).toContainText('Notification Preferences')
    await expect(page.getByRole('tabpanel')).toContainText('always remain enabled')

    await tabs.getByRole('tab', { name: 'Gameplay', exact: true }).click()
    await expect(page).toHaveURL(/tab=gameplay/)
    await expect(
      page.getByRole('switch', { name: 'Automatically pause when an incident starts' })
    ).toBeVisible()
    await expect(page.getByRole('tabpanel')).toContainText('Resume the guide')
    await expect(page.getByRole('tabpanel')).toContainText('Replay orientation')
    await page.reload()
    await expect(tabs.getByRole('tab', { name: 'Gameplay', exact: true })).toHaveAttribute(
      'aria-selected',
      'true'
    )
    await expect(page.getByRole('tabpanel')).not.toContainText('Color Theme')
  })
}
