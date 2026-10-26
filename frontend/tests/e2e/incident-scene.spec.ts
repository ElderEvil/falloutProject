import { test, expect } from '@playwright/test'

// The preview contract needs no backend image server.
test.beforeEach(async ({ page }) => {
  await page.route('**/static/**', (route) =>
    route.fulfill({
      contentType: 'image/svg+xml',
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect width="100" height="100" fill="green"/></svg>',
    })
  )
})

for (const [width, count] of [
  [390, 6],
  [900, 6],
  [390, 12],
  [900, 12],
]) {
  test(`${count} room residents and helpers fit the preview at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.goto(`/tests/e2e/fixtures/incident-scene.html?responders=${count}`)
    const scene = page.getByRole('region', { name: 'Incident live status' })
    await expect(scene).toContainText(`RESPONDERS · ${count}`)
    await expect(scene.locator('.dweller-name-badge')).toHaveCount(count)
    await expect(scene.locator('.dweller-health')).toHaveCount(count)
    await expect(scene.getByAltText('Deathclaw', { exact: true })).toBeVisible()
    await expect(scene.locator('.floating-effect').first().locator('..')).toHaveCSS(
      'overflow-y',
      'visible'
    )
    const bounds = (await scene.boundingBox())!
    const actors = scene.locator('.incident-responder')
    const first = (await actors.first().boundingBox())!
    for (const actor of await actors.all()) {
      const box = (await actor.boundingBox())!
      expect(Math.abs(box.y + box.height - first.y - first.height)).toBeLessThan(1)
      expect(box.y).toBeGreaterThan(bounds.y + 25)
      expect(box.y + box.height).toBeLessThan(bounds.y + bounds.height - 45)
    }
    await actors.last().scrollIntoViewIfNeeded()
    await expect(actors.last()).toBeInViewport()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })
}

test('room art falls back and fire respects reduced motion', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/tests/e2e/fixtures/incident-scene.html?type=fire&fallback')
  const scene = page.getByRole('region', { name: 'Incident live status' })
  await expect(scene).toContainText('ROOM HAZARD')
  await expect(scene.locator('.scene-backdrop')).toHaveAttribute('src', /FOS Diner/)
  await expect(scene.locator('.flame-outer')).toHaveCSS('animation-name', 'none')
  await expect(scene.getByRole('progressbar', { name: 'Contained' })).toHaveAttribute(
    'aria-valuenow',
    '35'
  )
})

for (const width of [390, 900]) {
  test(`incident creature size is independent of intrinsic artwork at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.route('**/static/creature_images/**', (route) =>
      route.fulfill({
        contentType: 'image/svg+xml',
        body: '<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024"><rect width="1024" height="1024" fill="green"/></svg>',
      })
    )
    await page.goto('/tests/e2e/fixtures/incident-scene.html?responders=6')
    const scene = page.getByRole('region', { name: 'Incident live status' })
    const creature = scene.getByAltText('Deathclaw', { exact: true })
    await expect.poll(() => creature.evaluate((el: HTMLImageElement) => el.naturalWidth)).toBe(1024)
    const bounds = (await creature.boundingBox())!
    const frame = (await scene.boundingBox())!
    expect(bounds.height).toBeLessThan(frame.height * 0.7)
    expect(bounds.height).toBeGreaterThan(100)
    expect(bounds.y).toBeGreaterThan(frame.y + 32)
    expect(bounds.y + bounds.height).toBeLessThan(frame.y + frame.height - 30)
  })
}
