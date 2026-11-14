import { test, expect, type Page } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { setAuthToken, TEST_USER } from './fixtures/auth'

const TOKEN = 'deterministic-e2e-token'

// WCAG 2.1 A/AA is the mainstream target; axe's best-practice rules stay off so the
// gate tracks a published standard instead of tarpaulin preferences.
const WCAG_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']

async function mockApi(page: Page) {
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname

    if (path === '/api/v1/users/me') return route.fulfill({ json: TEST_USER })
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
 */
async function expectNoViolations(page: Page, label: string) {
  await expect(page.locator('svg.iconify path').first()).toBeVisible({ timeout: 20000 })

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

    await expectNoViolations(page, '/login')
  })

  test('register', async ({ page }) => {
    await mockApi(page)
    await page.goto('/register')

    await expectNoViolations(page, '/register')
  })

  test('home', async ({ page }) => {
    await mockApi(page)
    await page.goto('/login')
    await setAuthToken(page, TOKEN, TEST_USER)
    await page.goto('/')

    await expectNoViolations(page, '/')
  })
})
