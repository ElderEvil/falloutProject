import { expect, test } from '@playwright/test'
import { staticFile } from './support/api'

test.beforeEach(async ({ page }) => {
  await page.route('**/static/**', (route) =>
    route.fulfill({
      path: staticFile(new URL(route.request().url()).pathname.replace('/static/', '')),
    })
  )
  await page.route('**/api/v1/**', (route) => {
    const url = route.request().url()
    if (url.includes('/incidents/') && url.endsWith('/team')) {
      return route.fulfill({ json: [] })
    }
    return route.fulfill({ json: {} })
  })
})

for (const [width, height] of [
  [1280, 720],
  [1280, 900],
  [390, 844],
] as const) {
  test(`incident detail keeps the fight inside the modal at ${width}x${height}`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height })
    await page.goto('/tests/e2e/fixtures/incident-detail.html?responders=4&helpers=3')

    const scene = page.getByRole('region', { name: 'Incident live status' })
    await expect(scene).toBeVisible()
    await expect(page.getByRole('button', { name: 'Suggest squad' })).toBeVisible()
    const body = page.locator('#modal-body')
    const metrics = await body.evaluate((element) => ({
      clientHeight: element.clientHeight,
      scrollHeight: element.scrollHeight,
      clientWidth: element.clientWidth,
      scrollWidth: element.scrollWidth,
    }))
    const verticalOverflow = metrics.scrollHeight - metrics.clientHeight
    expect(verticalOverflow).toBeLessThanOrEqual(height >= 900 ? 1 : 100)
    expect(metrics.scrollWidth).toBeLessThanOrEqual(metrics.clientWidth + 1)

    const row = scene.locator('.incident-responder').first().locator('..')
    const rowMetrics = await row.evaluate((element) => ({
      clientWidth: element.clientWidth,
      scrollWidth: element.scrollWidth,
    }))
    expect(rowMetrics.scrollWidth).toBeLessThanOrEqual(rowMetrics.clientWidth + 1)

    const sceneBox = (await scene.boundingBox())!
    const logSummary = page.getByText(/Battle log · \d+ entries/)
    await expect(logSummary).toBeVisible()
    await expect(page.getByLabel('Battle journal')).not.toHaveAttribute('open', '')
    const summaryBox = (await logSummary.boundingBox())!
    expect(summaryBox.y).toBeGreaterThanOrEqual(sceneBox.y + sceneBox.height - 1)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })
}
