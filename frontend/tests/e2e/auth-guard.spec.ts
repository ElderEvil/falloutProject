import { test, expect, type Page } from '@playwright/test'
import { TEST_USER, type TestUser } from './fixtures/auth'

const TOKEN = 'deterministic-e2e-token'

/**
 * A signed-in Overseer *without* superuser rights. Anonymous requests prove nothing
 * about authorisation: they are stopped by the requiresAuth branch before
 * requiresSuperuser is ever consulted, so the admin gate needs a real session.
 */
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

/**
 * Stub the API surface the shell touches on boot. CI runs this spec with
 * PW_SKIP_BACKEND=1 (Vite only), so every request must be answered here.
 */
async function mockApi(page: Page, user: TestUser | null): Promise<void> {
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname

    if (path === '/api/v1/users/me') {
      if (!user) return route.fulfill({ status: 401, json: { detail: 'Not authenticated' } })
      return route.fulfill({ json: user })
    }
    if (path === '/api/v1/users/me/profile') return route.fulfill({ json: PROFILE })
    if (path === '/api/v1/auth/oauth/providers') {
      return route.fulfill({ json: { google: false, github: false } })
    }
    if (path === '/api/v1/vaults/my') return route.fulfill({ json: [] })
    // Collection endpoints the dashboard/store layer iterates; an object stub here
    // throws `forEach is not a function` and would be misread as a guard failure.
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

/**
 * Seed the session *before* the app boots: the auth store freezes
 * `initialization` at creation time, so a token written after hydration is not
 * consulted by the first guard pass.
 */
async function signInBeforeLoad(page: Page, user: TestUser): Promise<void> {
  await page.addInitScript(
    ([token, user]) => {
      localStorage.setItem('token', token)
      localStorage.setItem('user', JSON.stringify(user))
    },
    [TOKEN, user] as const
  )
}

/** Records JS crashes so a guard that "redirects" by blowing up cannot pass. */
function trackPageErrors(page: Page): string[] {
  const errors: string[] = []
  page.on('pageerror', (err) => errors.push(`PAGE ERROR: ${err.message}`))
  return errors
}

async function expectNoCrash(page: Page, errors: string[]): Promise<void> {
  expect(errors).toHaveLength(0)
  await expect(page.locator('#vite-error-overlay')).toHaveCount(0)
  await expect(page.locator('body')).not.toBeEmpty()
}

/**
 * All auth-protected routes that must redirect to /login when not authenticated.
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
  { url: '/vault/fake-id/quests?claimQuest=test-id', name: 'quest-reward-claim' },
  { url: '/vault/fake-id/objectives', name: 'objectives' },
  { url: '/vault/fake-id/map', name: 'map' },
  { url: '/vault/fake-id/relationships', name: 'relationships' },
  { url: '/profile', name: 'profile' },
  { url: '/settings', name: 'settings' },
  { url: '/preferences', name: 'preferences' },
  { url: '/changelog', name: 'changelog' },
]

test.describe('Auth guard — unauthenticated deep routes redirect to /login', () => {
  for (const { url, name } of AUTH_ROUTES) {
    test(`${name} (${url}) redirects to /login`, async ({ page }) => {
      const pageErrors = trackPageErrors(page)
      await mockApi(page, null)

      await page.goto(url)
      await page.waitForURL('**/login**', { timeout: 10_000 })

      expect(new URL(page.url()).pathname).toBe('/login')
      await expectNoCrash(page, pageErrors)
    })
  }

  // Deepest zone route: a dweller conversation is per-dweller state, so it must be
  // gated even though it is reachable only from an already-guarded page.
  //
  // KNOWN ROUTER GAP: `chatRoutes` registers this path with `meta: { parentRoute }`
  // and no `requiresAuth`, so the beforeEach guard never fires for it and an
  // anonymous visitor renders the chat shell. `test.fail` keeps the expectation
  // recorded (and turns into a hard failure the moment the route is guarded, which
  // is the signal to drop the marker). Fixing it needs `meta.requiresAuth: true`
  // in src/modules/chat/routes — out of scope for this test-only PR.
  test.fail('dweller chat (/dweller/:id/chat) redirects to /login', async ({ page }) => {
    const pageErrors = trackPageErrors(page)
    await mockApi(page, null)

    await page.goto('/dweller/fake-id/chat')
    await page.waitForURL('**/login**', { timeout: 10_000 })

    expect(new URL(page.url()).pathname).toBe('/login')
    await expectNoCrash(page, pageErrors)
  })
})

test.describe('Auth guard — public routes stay reachable without a session', () => {
  for (const { url, name } of [
    { url: '/login', name: 'login' },
    { url: '/register', name: 'register' },
    { url: '/forgot-password', name: 'forgot-password' },
    { url: '/reset-password', name: 'reset-password' },
    { url: '/verify-email', name: 'verify-email' },
    { url: '/about', name: 'about' },
  ]) {
    test(`${name} stays on page without auth`, async ({ page }) => {
      await mockApi(page, null)

      await page.goto(url)
      await page.waitForLoadState('networkidle')

      expect(new URL(page.url()).pathname).toBe(url)
      await expect(page.locator('body')).toBeVisible({ timeout: 10_000 })
    })
  }
})

test.describe('Auth guard — signed-in users', () => {
  test('non-admin session is denied /admin/ai-settings and sent to /profile', async ({ page }) => {
    const pageErrors = trackPageErrors(page)
    await mockApi(page, NON_ADMIN_USER)
    await signInBeforeLoad(page, NON_ADMIN_USER)

    await page.goto('/admin/ai-settings')
    await page.waitForURL('**/profile**', { timeout: 10_000 })

    expect(new URL(page.url()).pathname).toBe('/profile')
    // The admin surface must never have rendered for a non-admin.
    await expect(page.getByRole('heading', { name: /AI Settings/i })).toHaveCount(0)
    await expectNoCrash(page, pageErrors)
  })

  test('superuser session reaches /admin/ai-settings', async ({ page }) => {
    await mockApi(page, TEST_USER)
    await signInBeforeLoad(page, TEST_USER)

    await page.goto('/admin/ai-settings')
    await page.waitForLoadState('networkidle')

    expect(new URL(page.url()).pathname).toBe('/admin/ai-settings')
  })

  test('signed-in non-admin reaches a protected route', async ({ page }) => {
    const pageErrors = trackPageErrors(page)
    await mockApi(page, NON_ADMIN_USER)
    await signInBeforeLoad(page, NON_ADMIN_USER)

    await page.goto('/vault/fake-id/happiness')
    await page.waitForLoadState('networkidle')

    expect(new URL(page.url()).pathname).toBe('/vault/fake-id/happiness')
    await expectNoCrash(page, pageErrors)
  })
})
