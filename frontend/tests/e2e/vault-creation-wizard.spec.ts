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
    await page.route('**/api/v1/**', async (route) => {
      const path = new URL(route.request().url()).pathname
      if (path === '/api/v1/vaults/initiate') {
        creations.push(route.request().postDataJSON())
        return route.fulfill({ status: 400, json: { detail: 'This vault number is unavailable' } })
      }
      if (path === '/api/v1/vaults/my') return route.fulfill({ json: [] })
      if (path === '/api/v1/users/me') return route.fulfill({ json: TEST_USER })
      if (path.startsWith('/api/v1/stream/')) {
        return route.fulfill({ contentType: 'text/event-stream', body: ': connected\n\n' })
      }
      return route.fulfill({ json: {} })
    })
    await page.goto('/')
    const input = page.getByLabel('Vault Number', { exact: true })
    await expect(input).toBeFocused()
    await expect(page.getByRole('button', { name: 'Create Vault', exact: true })).toHaveCount(0)
    await page.evaluate(() => window.scrollTo(0, 0))
    await page.screenshot({
      path: `/tmp/fallout-vault-wizard-number-${width}.png`,
      fullPage: true,
      animations: 'disabled',
    })
    await input.fill('68')
    await input.press('Enter')
    const setupHeading = page.getByRole('heading', { name: 'Choose how you start' })
    await expect(setupHeading).toBeFocused()
    await page.evaluate(() => window.scrollTo(0, 0))
    await page.screenshot({
      path: `/tmp/fallout-vault-wizard-setup-${width}.png`,
      fullPage: true,
      animations: 'disabled',
    })
    await page.getByRole('switch', { name: /Boosted Start/ }).click()
    await page.getByRole('button', { name: 'Survival', exact: false }).click()
    await expect(page.getByLabel('Boosted Start')).toBeDisabled()
    await expect(page.getByRole('switch', { name: /Boosted Start/ })).toHaveAttribute(
      'aria-checked',
      'false'
    )
    await page.getByRole('button', { name: 'Continue', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Ready to open the doors?' })).toBeFocused()
    await expect(page.getByText('068', { exact: true })).toBeVisible()
    await expect(page.getByText('Build from scratch', { exact: true })).toBeVisible()
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
    expect(creations[0]).toEqual({ number: 68, boosted: false, vault_mode: 'survival' })
    await expect(page.getByRole('button', { name: 'Create Vault', exact: true })).toBeEnabled()
    await page.getByRole('button', { name: 'Back', exact: true }).click()
    await page.getByRole('button', { name: 'Back', exact: true }).click()
    await expect(input).toHaveValue('68')
    await expect(input).toBeFocused()
  })
}
