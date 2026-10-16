import { test, expect, type Page } from '@playwright/test'
import { setAuthToken, type TestUser } from './fixtures/auth'

// Browser coverage for the spotlight guide (#1001): the card and cut-out must
// coexist with the real vault UI at phone width, and the guide must yield to a
// dialog without losing the pending lesson. All backend traffic is mocked, so
// the assertions depend only on frontend markup and state.
test.use({
  locale: 'en-US',
  timezoneId: 'UTC',
  viewport: { width: 1280, height: 900 },
})

const TOKEN = 'deterministic-e2e-token'

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
  radio_mode: 'happiness',
  created_at: '2026-01-15T10:30:00Z',
  updated_at: '2026-01-15T10:30:00Z',
  resource_warnings: [],
  room_count: 1,
  dweller_count: 8,
  stimpack: 4,
  radaway: 2,
}

async function mockApi(page: Page) {
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname

    if (path === '/api/v1/users/me') return route.fulfill({ json: AUTH_USER })
    if (path === '/api/v1/vaults/my') return route.fulfill({ json: [VAULT] })
    if (path === '/api/v1/vaults/vault-1') return route.fulfill({ json: VAULT })
    if (path === '/api/v1/notifications/unread-count') return route.fulfill({ json: { count: 0 } })
    if (path === '/api/v1/notifications/') return route.fulfill({ json: [] })
    if (path.startsWith('/api/v1/stream/')) {
      return route.fulfill({ contentType: 'text/event-stream', body: ': connected\n\n' })
    }
    // Everything else the vault shell polls is benign when empty.
    return route.fulfill({ json: [] })
  })
}

async function openVault(page: Page) {
  await page.addInitScript(() => {
    // Opt this vault into the orientation and seed the "What's New" key so the
    // changelog modal never races the guide.
    window.localStorage.setItem('onboarding:v1', JSON.stringify({ 'vault-1': { created: true } }))
    window.localStorage.setItem('fallout_changelog_last_seen', '999.0.0')
  })
  await mockApi(page)
  await page.goto('/login')
  await setAuthToken(page, TOKEN, AUTH_USER)
  await page.goto('/vault/vault-1')
}

test.describe('Spotlight guide — vault page', () => {
  test('shows the guide and highlights an on-screen control at phone width', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await openVault(page)

    await expect(page.getByText('Welcome, Overseer')).toBeVisible({ timeout: 15000 })
    await page.getByRole('button', { name: 'Start' }).click()

    const card = page.locator('.onboarding-card')
    await expect(card).toBeVisible()
    await expect(card).toContainText('Keep the power on')

    // The guide must not cover the control it points at.
    const cutout = page.locator('.onboarding-cutout')
    await expect(cutout).toBeAttached({ timeout: 10000 })
    const cutoutBox = await cutout.boundingBox()
    const cardBox = await card.boundingBox()
    expect(cutoutBox).not.toBeNull()
    expect(cardBox).not.toBeNull()
    const overlaps =
      cutoutBox!.x < cardBox!.x + cardBox!.width &&
      cutoutBox!.x + cutoutBox!.width > cardBox!.x &&
      cutoutBox!.y < cardBox!.y + cardBox!.height &&
      cutoutBox!.y + cutoutBox!.height > cardBox!.y
    expect(overlaps).toBe(false)
  })

  test('yields the guide to a dialog and resumes the same lesson', async ({ page }) => {
    await openVault(page)
    await expect(page.getByText('Welcome, Overseer')).toBeVisible({ timeout: 15000 })
    await page.getByRole('button', { name: 'Start' }).click()

    const card = page.locator('.onboarding-card')
    await expect(card).toBeVisible()

    // The notification panel is a dialog-role overlay; the guide must give way.
    await page.getByRole('button', { name: 'Notifications' }).click()
    await expect(page.getByRole('dialog', { name: 'Notifications' })).toBeVisible()
    await expect(card).toHaveCount(0)

    await page.keyboard.press('Escape')
    await expect(page.getByRole('dialog', { name: 'Notifications' })).toHaveCount(0)
    await expect(card).toBeVisible()
    await expect(card).toContainText('Keep the power on')
  })
})
