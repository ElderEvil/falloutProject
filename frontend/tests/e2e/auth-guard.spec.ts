import { test, expect, type Page } from '@playwright/test'
import type { AISettingsRead } from '../../src/modules/ai-settings/models/aiSettings'
import type { DeathStatistics } from '../../src/core/types/death'
import { TEST_USER, type TestUser } from './fixtures/auth'

const TOKEN = 'deterministic-e2e-token'
const AI_SETTINGS_URL = '/api/v1/ai-settings/'
const ADMIN_PANEL_MARKER = 'Provider configuration'

const AI_SETTINGS: AISettingsRead = {
  profile: null,
  effective: {
    provider: 'openai',
    model: 'gpt-4o-mini',
    base_url: null,
    gateway_route: 'openai',
    mode: 'gateway',
  },
  jev: {
    enabled: true,
    configured: true,
    model: 'gpt-4o-mini',
    timeout_seconds: 10,
  },
}

const NON_ADMIN_USER: TestUser = {
  ...TEST_USER,
  id: 'non-admin-user-id',
  email: 'overseer@example.com',
  is_superuser: false,
}

const PROFILE = {
  id: 'test-user-id',
  user_id: 'test-user-id',
  bio: 'Overseer of Vault 42',
  avatar_url: null,
  preferences: { setup: { version: 1, completed: true, skipped: false } },
  total_dwellers_created: 0,
  total_caps_earned: 0,
  total_explorations: 0,
  total_rooms_built: 0,
  total_incidents: 0,
  total_incidents_won: 0,
  total_incidents_lost: 0,
  total_dwellers_born: 0,
  total_dwellers_died: 0,
  deaths_by_health: 0,
  deaths_by_radiation: 0,
  deaths_by_incident: 0,
  deaths_by_exploration: 0,
  deaths_by_combat: 0,
  created_at: '2026-01-15T10:30:00Z',
  updated_at: '2026-02-01T08:00:00Z',
}

const DEATH_STATISTICS: DeathStatistics = {
  total_dwellers_born: 0,
  total_dwellers_died: 0,
  deaths_by_cause: { health: 0, radiation: 0, incident: 0, exploration: 0, combat: 0 },
  revivable_count: 0,
  permanently_dead_count: 0,
}

async function mockApi(page: Page, user: TestUser | null): Promise<void> {
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname

    if (path === '/api/v1/users/me') {
      if (!user) return route.fulfill({ status: 401, json: { detail: 'Not authenticated' } })
      return route.fulfill({ json: user })
    }
    if (path === '/api/v1/users/me/profile') return route.fulfill({ json: PROFILE })
    if (path === '/api/v1/users/me/profile/statistics') {
      return route.fulfill({ json: DEATH_STATISTICS })
    }
    if (path === '/api/v1/auth/oauth/providers') {
      return route.fulfill({ json: { google: false, github: false } })
    }
    if (path === '/api/v1/auth/oauth/accounts') {
      return route.fulfill({ json: { providers: [], has_password: true } })
    }
    if (path === '/api/v1/vaults/my') return route.fulfill({ json: [] })
    if (path === '/api/v1/ai-settings/') return route.fulfill({ json: AI_SETTINGS })
    if (path === '/api/v1/dwellers' || path.startsWith('/api/v1/dwellers/vault/')) {
      return route.fulfill({ json: [] })
    }
    if (path === '/api/v1/notifications/unread-count') {
      return route.fulfill({ json: { count: 0 } })
    }
    if (path === '/api/v1/notifications/') return route.fulfill({ json: [] })
    if (path.startsWith('/api/v1/stream/')) {
      return route.fulfill({ contentType: 'text/event-stream', body: ': connected\n\n' })
    }

    return route.fulfill({ json: {} })
  })
}

/** Stubs the API, seeds an optional session, and returns any uncaught page errors. */
async function prepareAs(page: Page, user: TestUser | null): Promise<string[]> {
  const errors: string[] = []
  page.on('pageerror', (err) => errors.push(`PAGE ERROR: ${err.message}`))
  await mockApi(page, user)
  // `initialization` freezes at store creation, so a token added later misses the first guard pass.
  if (user) {
    await page.addInitScript(
      ([token, user]) => {
        localStorage.setItem('token', token)
        localStorage.setItem('user', JSON.stringify(user))
      },
      [TOKEN, user] as const
    )
  }
  return errors
}

function trackAiSettingsRequests(page: Page): string[] {
  const hits: string[] = []
  page.on('request', (request) => {
    if (new URL(request.url()).pathname === AI_SETTINGS_URL) hits.push(request.method())
  })
  return hits
}

async function expectNoCrash(page: Page, errors: string[]): Promise<void> {
  expect(errors).toHaveLength(0)
  await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
  await expect(page.locator('body')).not.toBeEmpty()
}

const AUTH_ROUTES: [name: string, url: string][] = [
  ['home', '/'],
  ['vault', '/vault/fake-id'],
  ['happiness', '/vault/fake-id/happiness'],
  ['storage', '/vault/fake-id/storage'],
  ['dwellers', '/vault/fake-id/dwellers'],
  ['dweller-detail', '/vault/fake-id/dwellers/test-id'],
  ['dweller-chat', '/dweller/fake-id/chat'],
  ['graveyard', '/vault/fake-id/dwellers/graveyard'],
  ['exploration', '/vault/fake-id/exploration'],
  ['exploration-detail', '/vault/fake-id/exploration/test-id'],
  ['training', '/vault/fake-id/training'],
  ['quests', '/vault/fake-id/quests'],
  ['quest-reward-claim', '/vault/fake-id/quests?claimQuest=test-id'],
  ['objectives', '/vault/fake-id/objectives'],
  ['map', '/vault/fake-id/map'],
  ['relationships', '/vault/fake-id/relationships'],
  ['profile', '/profile'],
  ['settings', '/settings'],
  ['preferences', '/preferences'],
  ['changelog', '/changelog'],
]

const PUBLIC_ROUTES: [name: string, url: string][] = [
  ['login', '/login'],
  ['register', '/register'],
  ['forgot-password', '/forgot-password'],
  ['reset-password', '/reset-password'],
  ['verify-email', '/verify-email'],
  ['about', '/about'],
]

test.describe('Auth guard — unauthenticated deep routes redirect to /login', () => {
  for (const [name, url] of AUTH_ROUTES) {
    test(`${name} (${url}) redirects to /login`, async ({ page }) => {
      const pageErrors = await prepareAs(page, null)

      await page.goto(url)
      await page.waitForURL('**/login**', { timeout: 10_000 })

      expect(new URL(page.url()).pathname).toBe('/login')
      await expectNoCrash(page, pageErrors)
    })
  }
})

test.describe('Auth guard — public routes stay reachable without a session', () => {
  for (const [name, url] of PUBLIC_ROUTES) {
    test(`${name} stays on page without auth`, async ({ page }) => {
      await mockApi(page, null)

      await page.goto(url)
      await page.waitForLoadState('networkidle')

      expect(new URL(page.url()).pathname).toBe(url)
      await expect(page.locator('body')).toBeVisible({ timeout: 10_000 })
    })
  }
})

test.describe('Routing — unknown addresses', () => {
  test('render the 404 view instead of doing nothing', async ({ page }) => {
    await mockApi(page, null)

    await page.goto('/definitely-not-a-route')
    await page.waitForLoadState('networkidle')

    // The address stays put: a caught 404 must not bounce the player to the vault.
    expect(new URL(page.url()).pathname).toBe('/definitely-not-a-route')
    await expect(page.getByRole('heading', { name: /route not found/i })).toBeVisible({
      timeout: 10_000,
    })
  })
})

test.describe('Auth guard — signed-in users', () => {
  test('non-admin session is denied /admin/ai-settings and sent to /profile', async ({ page }) => {
    const pageErrors = await prepareAs(page, NON_ADMIN_USER)
    const aiSettingsRequests = trackAiSettingsRequests(page)

    await page.goto('/admin/ai-settings')
    await page.waitForURL('**/profile**', { timeout: 10_000 })
    await page.waitForLoadState('networkidle')

    expect(new URL(page.url()).pathname).toBe('/profile')
    // Zero requests prove no ai-settings fetch fired: the router never mounted the view.
    expect(aiSettingsRequests).toHaveLength(0)
    await expectNoCrash(page, pageErrors)
  })

  test('superuser session reaches /admin/ai-settings and the panel renders', async ({ page }) => {
    const pageErrors = await prepareAs(page, TEST_USER)
    const settingsRequest = page.waitForRequest(
      (request) => new URL(request.url()).pathname === AI_SETTINGS_URL,
      { timeout: 10_000 }
    )

    await page.goto('/admin/ai-settings')
    expect((await settingsRequest).method()).toBe('GET')

    await page.waitForURL('**/admin/ai-settings', { timeout: 10_000 })
    expect(new URL(page.url()).pathname).toBe('/admin/ai-settings')
    await expect(page.getByText(ADMIN_PANEL_MARKER, { exact: true })).toBeVisible()
    await expect(page.getByText('Effective configuration', { exact: true })).toBeVisible()
    await expect(page.locator('#ai-model')).toBeVisible()
    await expect(page.getByText('AI settings unavailable')).toHaveCount(0)
    await expect(page.getByText('gpt-4o-mini', { exact: true }).first()).toBeVisible()
    await expectNoCrash(page, pageErrors)
  })

  test('signed-in non-admin reaches a protected route', async ({ page }) => {
    const pageErrors = await prepareAs(page, NON_ADMIN_USER)

    await page.goto('/vault/fake-id/happiness')
    await page.waitForLoadState('networkidle')

    expect(new URL(page.url()).pathname).toBe('/vault/fake-id/happiness')
    await expectNoCrash(page, pageErrors)
  })
})
