import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'

const staticFile = (url: string) => {
  const pathname = decodeURIComponent(new URL(url).pathname).replace(/^\/static\//, '')
  return fileURLToPath(new URL(`../../../backend/app/static/${pathname}`, import.meta.url))
}

test.beforeEach(async ({ page }) => {
  await page.route('**/static/**', (route) =>
    route.fulfill({ path: staticFile(route.request().url()) })
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
    await expect(page.getByRole('button', { name: /Send strongest/ })).toBeVisible()
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

    const sceneBox = (await scene.boundingBox())!
    const logSummary = page.getByText(/Battle log · \d+ entries/)
    await expect(logSummary).toBeVisible()
    await expect(page.getByLabel('Battle journal')).not.toHaveAttribute('open', '')
    const summaryBox = (await logSummary.boundingBox())!
    expect(summaryBox.y).toBeGreaterThanOrEqual(sceneBox.y + sceneBox.height - 1)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })
}
