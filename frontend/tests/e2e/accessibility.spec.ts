import { test, expect, type Page } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { setAuthToken, TEST_USER } from './fixtures/auth'

const TOKEN = 'deterministic-e2e-token'

// WCAG 2.1 A/AA is the mainstream target; axe's best-practice rules stay off so the
// gate tracks a published standard instead of tarpaulin preferences.
const WCAG_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']

// Completed setup keeps HomeView on the vault dashboard instead of the async
// FirstRunSetupModal, which would otherwise replace the surface under test.
const PROFILE = {
  id: 'test-user-id',
  user_id: 'test-user-id',
  bio: 'Overseer of Vault 42',
  avatar_url: null,
  preferences: { setup: { version: 1, completed: true, skipped: false } },
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

async function mockApi(page: Page) {
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname

    if (path === '/api/v1/users/me') return route.fulfill({ json: TEST_USER })
    if (path === '/api/v1/users/me/profile') return route.fulfill({ json: PROFILE })
    if (path === '/api/v1/auth/oauth/providers') {
      return route.fulfill({ json: { google: false, github: false } })
    }
    if (path === '/api/v1/vaults/my') return route.fulfill({ json: [] })
    if (path === '/api/v1/notifications/unread-count') return route.fulfill({ json: { count: 0 } })
    if (path === '/api/v1/notifications/') return route.fulfill({ json: [] })
    if (path.startsWith('/api/v1/stream/')) {
      return route.fulfill({ contentType: 'text/event-stream', body: ': connected\n\n' })
    }

    return route.fulfill({ json: {} })
  })
}

/**
 * Axe over the rendered DOM: this is the only check that sees Vue templates, since
 * Oxlint's jsx-a11y plugin parses script blocks and never template markup.
 *
 * Callers wait for their own route content first. A shared icon wait is not
 * readiness: lazily imported route components mount after the shell, so axe would
 * scan an incomplete page.
 */
async function expectNoViolations(page: Page, label: string) {
  const { violations } = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze()
  const summary = violations
    .map((violation) => {
      const nodes = violation.nodes.map((node) => node.target.join(' ')).join(' | ')
      return `${violation.id} (${violation.impact}) ${violation.help} -> ${nodes}`
    })
    .join('\n')

  expect(violations, `${label} accessibility violations:\n${summary}`).toEqual([])
}

test.describe('accessibility — entry routes', () => {
  test('login', async ({ page }) => {
    await mockApi(page)
    await page.goto('/login')
    await expect(page.getByRole('button', { name: 'AUTHENTICATE' })).toBeVisible()

    await expectNoViolations(page, '/login')
  })

  test('register', async ({ page }) => {
    await mockApi(page)
    await page.goto('/register')
    await expect(page.getByRole('button', { name: 'REGISTER OVERSEER' })).toBeVisible()

    await expectNoViolations(page, '/register')
  })

  test('home', async ({ page }) => {
    await mockApi(page)
    await page.goto('/login')
    await setAuthToken(page, TOKEN, TEST_USER)
    await page.goto('/')

    await expect(page.getByRole('heading', { name: 'Create New Vault' })).toBeVisible()
    await expect(page.getByText('Welcome, Overseer')).toHaveCount(0)

    await expectNoViolations(page, '/')
  })
})
