import { expect, test } from '@playwright/test'
import { TEST_USER } from './fixtures/auth'

for (const width of [1280, 375]) {
  test(`vault commissioning supports keyboard navigation at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.addInitScript((user) => {
      localStorage.setItem('token', 'wizard-test-token')
      localStorage.setItem('user', JSON.stringify(user))
      localStorage.setItem('fallout_changelog_last_seen', '999.0.0')
    }, TEST_USER)
    const creations: unknown[] = []
    let setupComplete = width === 1280
    await page.route('**/api/v1/**', async (route) => {
      const path = new URL(route.request().url()).pathname
      if (path === '/api/v1/vaults/initiate') {
        creations.push(route.request().postDataJSON())
        return route.fulfill({ status: 400, json: { detail: 'This vault number is unavailable' } })
      }
      if (path === '/api/v1/vaults/my') return route.fulfill({ json: [] })
      if (path === '/api/v1/vaults/scenarios') {
        return route.fulfill({
          json: [
            {
              number: 68,
              key: 'vault_68_test',
              title: 'Vault 68 — The Ratio',
              description: 'Start with eight male residents and one female resident.',
              default_boosted: false,
              expedition: false,
            },
          ],
        })
      }
      if (path === '/api/v1/users/me') return route.fulfill({ json: TEST_USER })
      if (path === '/api/v1/users/me/profile') {
        if (route.request().method() === 'PUT') setupComplete = true
        return route.fulfill({
          json: { preferences: { setup: { version: 1, completed: setupComplete } } },
        })
      }
      if (path.startsWith('/api/v1/stream/')) {
        return route.fulfill({ contentType: 'text/event-stream', body: ': connected\n\n' })
      }
      return route.fulfill({ json: {} })
    })
    await page.goto('/')
    const input = page.getByLabel('Vault Number', { exact: true })
    if (!setupComplete) {
      const setup = page.getByRole('dialog', { name: 'Welcome, Overseer' })
      await expect(setup).toBeVisible()
      await expect(input).toHaveCount(0)
      await setup.getByRole('button', { name: 'Skip for now' }).click()
    }
    await expect(input).toBeFocused()
    await expect(page.getByRole('button', { name: 'Create Vault', exact: true })).toHaveCount(0)
    await page.evaluate(() => window.scrollTo(0, 0))
    await page.screenshot({
      path: `/tmp/fallout-vault-wizard-number-${width}.png`,
      fullPage: true,
      animations: 'disabled',
    })
    const random = page.getByRole('button', { name: 'Random vault number' })
    await random.focus()
    await random.press('Space')
    await expect(input).toHaveValue(/^[1-9]\d{0,2}$/)
    expect(creations).toHaveLength(0)
    const experiment = page.getByRole('button', { name: 'Vault 68 — The Ratio' })
    await experiment.focus()
    await experiment.press('Enter')
    const setupHeading = page.getByRole('heading', { name: 'Choose your vault mode' })
    await expect(setupHeading).toBeFocused()
    await page.evaluate(() => window.scrollTo(0, 0))
    await page.screenshot({
      path: `/tmp/fallout-vault-wizard-setup-${width}.png`,
      fullPage: true,
      animations: 'disabled',
    })
    await page.getByRole('button', { name: 'Survival', exact: false }).click()
    await expect(page.getByRole('switch', { name: /Boosted Start/ })).toHaveCount(0)
    await expect(page.getByRole('switch', { name: /Vault 68/ })).toHaveAttribute(
      'aria-checked',
      'true'
    )
    await page.getByRole('button', { name: 'Continue', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Ready to open the doors?' })).toBeFocused()
    await expect(page.getByText('068', { exact: true })).toBeVisible()
    await expect(page.getByText('Vault 68 — The Ratio', { exact: true })).toBeVisible()
    expect(creations).toHaveLength(0)
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)
    ).toBe(true)
    await page.evaluate(() => window.scrollTo(0, 0))
    await page.screenshot({
      path: `/tmp/fallout-vault-wizard-review-${width}.png`,
      fullPage: true,
      animations: 'disabled',
    })
    await page.getByRole('button', { name: 'Create Vault', exact: true }).click()
    await expect.poll(() => creations.length).toBe(1)
    expect(creations[0]).toEqual({
      number: 68,
      boosted: false,
      vault_mode: 'survival',
      scenario: 'vault_68_test',
    })
    await expect(page.getByRole('button', { name: 'Create Vault', exact: true })).toBeEnabled()
    await page.getByRole('button', { name: 'Back', exact: true }).click()
    await page.getByRole('button', { name: 'Back', exact: true }).click()
    await expect(input).toHaveValue('68')
    await expect(input).toBeFocused()
  })
}
