import { test, expect, type Page } from '@playwright/test'
import { setAuthToken, type TestUser } from './fixtures/auth'

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

const AUTH_USER: TestUser = {
  id: 'test-user-id',
  username: 'overseer',
  email: 'overseer@vault-tec.com',
  is_active: true,
  is_superuser: true,
  email_verified: true,
}

const VAULT = {
  id: 'vault-1',
  number: 42,
  bottle_caps: 1250,
  happiness: 82,
  power: 80,
  power_max: 100,
  food: 70,
  food_max: 100,
  water: 18,
  water_max: 100,
  population_max: 10,
  radio_mode: 'recruitment',
  created_at: '2026-01-15T10:30:00Z',
  updated_at: '2026-01-15T10:30:00Z',
  resource_warnings: [],
  room_count: 1,
  dweller_count: 8,
  stimpack: 4,
  radaway: 2,
}

const PROFILE = {
  id: 'test-user-id',
  user_id: 'test-user-id',
  bio: 'Overseer of Vault 42, keeping the lights on since the bombs fell.',
  avatar_url: null,
  preferences: null,
  total_dwellers_created: 42,
  total_caps_earned: 15234,
  total_explorations: 17,
  total_rooms_built: 26,
  total_incidents: 11,
  total_incidents_won: 7,
  total_incidents_lost: 4,
  total_dwellers_born: 9,
  total_dwellers_died: 4,
  deaths_by_health: 1,
  deaths_by_radiation: 1,
  deaths_by_incident: 1,
  deaths_by_exploration: 1,
  deaths_by_combat: 0,
  created_at: '2026-01-15T10:30:00Z',
  updated_at: '2026-02-01T08:00:00Z',
}

const DEATH_STATISTICS = {
  total_dwellers_born: 9,
  total_dwellers_died: 4,
  deaths_by_cause: {
    health: 1,
    radiation: 1,
    incident: 1,
    exploration: 1,
    combat: 0,
  },
  revivable_count: 2,
  permanently_dead_count: 2,
}

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

async function mockApi(page: Page) {
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname

    if (path === '/api/v1/users/me/profile') return route.fulfill({ json: PROFILE })
    if (path === '/api/v1/users/me/profile/statistics') {
      return route.fulfill({ json: DEATH_STATISTICS })
    }
    if (path === '/api/v1/users/me/profile/ai-usage') return route.fulfill({ json: AI_USAGE })
    if (path === '/api/v1/users/me') return route.fulfill({ json: AUTH_USER })
    if (path === '/api/v1/auth/oauth/providers') {
      return route.fulfill({ json: { google: false, github: false } })
    }
    if (path === '/api/v1/vaults/my') return route.fulfill({ json: [VAULT] })
    if (path === '/api/v1/notifications/unread-count') return route.fulfill({ json: { count: 0 } })
    if (path === '/api/v1/notifications/') return route.fulfill({ json: [] })
    if (path.startsWith('/api/v1/stream/')) {
      return route.fulfill({ contentType: 'text/event-stream', body: ': connected\n\n' })
    }

    throw new Error(`Unhandled API request: ${route.request().method()} ${path}`)
  })
}

async function signIn(page: Page) {
  await page.goto('/login')
  await setAuthToken(page, TOKEN, AUTH_USER)
}

// Regression guard for #747: one canonical overlay, full opacity, canonical
// gradient — a re-added per-view overlay or an `opacity-*` on this element fails here.
async function expectCanonicalChrome(page: Page) {
  // Iconify renders an empty <svg class="iconify"> until its icon body is fetched,
  // so without this wait a fresh page can be captured icon-less (CI vs local drift).
  await expect(page.locator('svg.iconify path').first()).toBeVisible({ timeout: 20000 })

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
    await signIn(page)
    await page.goto('/')
    await expect(page.getByRole('heading', { name: 'Your Vaults' })).toBeVisible({ timeout: 10000 })

    await expectCanonicalChrome(page)
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
    await signIn(page)
    await page.goto('/profile')
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

    await expectCanonicalChrome(page)
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
    await signIn(page)
    await page.goto('/preferences?tab=sound')

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
