import { test, expect } from '@playwright/test'

for (const width of [390, 1280]) {
  test(`ring depth, scale and themed activation at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.route('**/static/**', (route) =>
      route.fulfill({
        contentType: 'image/svg+xml',
        body: '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect width="100" height="100" fill="green"/></svg>',
      })
    )
    await page.goto('/tests/e2e/fixtures/arena-ring.html')
    const ring = page.getByRole('region', { name: 'Arena ring' })
    const actors = ring.locator('.ring-fighter')
    const front = await actors.nth(0).boundingBox()
    const rear = await actors.nth(1).boundingBox()
    expect(rear!.y + rear!.height).toBeLessThan(front!.y + front!.height)
    const large = await ring.getByAltText('deathclaw#0', { exact: true }).boundingBox()
    const small = await ring.getByAltText('radroach-swarm#1', { exact: true }).boundingBox()
    expect(large!.width).toBeGreaterThan(small!.width * 2)
    expect(large!.height).toBeGreaterThan(small!.height * 2)
    const activate = ring.getByRole('button', {
      name: 'Use Aimed Shot from Alpha on deathclaw#0',
      exact: true,
    })
    const themeColor = await ring
      .getByText('Alpha', { exact: true })
      .evaluate((el) => getComputedStyle(el).color)
    await expect(activate).toHaveCSS('color', themeColor)
    await activate.hover()
    const tooltip = page.locator('[data-slot="tooltip-content"]')
    await expect(tooltip).toBeVisible()
    await expect(tooltip).toContainText('Alpha · Aimed Shot')
    await expect(tooltip).toHaveCSS('color', themeColor)
    await activate.click()
    await expect(activate).toHaveCount(0)
    await expect(actors.nth(0)).toContainText('QUEUED')
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })
}

test('countdown is centered in the preview and clears when combat begins', async ({ page }) => {
  await page.route('**/static/**', (route) => route.abort())
  await page.goto('/tests/e2e/fixtures/arena-ring.html?countdown=3', {
    waitUntil: 'domcontentloaded',
  })
  const ring = page.getByRole('region', { name: 'Arena ring' })
  await expect(ring.getByRole('status')).toContainText('STARTING IN')
  await expect(ring.locator('.countdown-number')).toHaveText('3')
  const scene = await ring.boundingBox()
  const counter = await ring.locator('.countdown-number').boundingBox()
  expect(Math.abs(counter!.x + counter!.width / 2 - (scene!.x + scene!.width / 2))).toBeLessThan(2)
  await expect(ring.getByRole('button', { name: /from Alpha/ })).toHaveCount(0)
  await expect(ring.locator('.countdown-number')).toHaveCount(0)
  await expect(ring.getByRole('button', { name: /from Alpha/ })).toBeEnabled()
})
