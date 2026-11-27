import { test, expect, type Page } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { TEST_USER } from './fixtures/auth'
import { mockApi } from './support/api'
import { standardApi } from './support/data'
import { open, openAs } from './support/session'

const TOKEN = 'deterministic-e2e-token'

// WCAG 2.1 A/AA is the mainstream target; axe's best-practice rules stay off so the
// gate tracks a published standard instead of tarpaulin preferences.
const WCAG_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']

// The vault list stays empty so HomeView renders the create-vault dashboard under test.
const mockAccessibleApi = (page: Page) =>
  mockApi(page, standardApi({ user: TEST_USER, vaults: [], statistics: {} }))

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
    await mockAccessibleApi(page)
    await open(page, '/login')
    await expect(page.getByRole('button', { name: 'AUTHENTICATE' })).toBeVisible()

    await expectNoViolations(page, '/login')
  })

  test('register', async ({ page }) => {
    await mockAccessibleApi(page)
    await open(page, '/register')
    await expect(page.getByRole('button', { name: 'REGISTER OVERSEER' })).toBeVisible()

    await expectNoViolations(page, '/register')
  })

  test('home', async ({ page }) => {
    await mockAccessibleApi(page)
    await openAs(page, '/', { token: TOKEN, user: TEST_USER })

    await expect(page.getByRole('heading', { name: 'Create New Vault' })).toBeVisible()
    await expect(page.getByText('Welcome, Overseer')).toHaveCount(0)

    await expectNoViolations(page, '/')
  })
})
