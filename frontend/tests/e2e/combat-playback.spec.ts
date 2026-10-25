import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.clock.install()
  await page.clock.pauseAt(new Date())
  await page.goto('/tests/e2e/fixtures/combat-playback.html', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('region', { name: 'Arena ring' })).toBeVisible()
})

for (const width of [390, 1280]) {
  test(`Arena synchronizes skills, ordinary attacks and final KOs at ${width}px`, async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width, height: 1000 })
    const ring = page.getByRole('region', { name: 'Arena ring' })
    const bob = ring.getByRole('progressbar', { name: 'Bob HP' })
    const delta = ring.getByRole('progressbar', { name: 'Delta HP' })
    await page.getByRole('button', { name: 'Play Arena turn' }).click()
    await expect(bob).toHaveAttribute('aria-valuenow', '100')
    await expect(ring.locator('.damage-number')).toHaveCount(0)
    await page.clock.runFor(250)
    await expect(bob).toHaveAttribute('aria-valuenow', '92')
    await expect(delta).toHaveAttribute('aria-valuenow', '92')
    await expect(ring.locator('.damage-number')).toHaveCount(2)
    await page.clock.runFor(450)
    await expect(bob).toHaveAttribute('aria-valuenow', '88')
    await page.clock.runFor(350)
    await expect(delta).toHaveAttribute('aria-valuenow', '87')
    await page.clock.runFor(200)
    await page.getByRole('button', { name: 'Finish Arena' }).click()
    await expect(ring).toBeVisible()
    await page.clock.runFor(250)
    await expect(bob).toHaveAttribute('aria-valuenow', '0')
    await expect(ring.getByText('KO', { exact: true })).toHaveCount(2)
    await page.screenshot({
      path: testInfo.outputPath(`combat-impact-${width}.png`),
      fullPage: true,
    })
    await page.clock.runFor(300)
    await expect(page.getByRole('status')).toHaveText('Arena complete')
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })

  test(`incident responders attack individually without skills at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 })
    const scene = page.getByRole('region', { name: 'Incident live status' })
    await page.getByRole('button', { name: 'Play incident round' }).click()
    const actors = scene.locator('.incident-responder')
    await expect(actors.nth(0)).toHaveAttribute('aria-current', 'true')
    await expect(actors.nth(1)).not.toHaveAttribute('aria-current', 'true')
    await page.clock.runFor(350)
    await expect(actors.nth(1)).toHaveAttribute('aria-current', 'true')
    await page.clock.runFor(499)
    await expect(scene).not.toContainText('Alice: 90')
    await page.clock.runFor(1)
    await expect(scene).toContainText('Alice: 90 of 100 HP')
    await expect(actors.nth(1).locator('.damage-number')).toHaveCount(0)
    await expect(scene.getByRole('button')).toHaveCount(0)
  })
}

test('reduced motion keeps impacts readable without moving effects', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.getByRole('button', { name: 'Play Arena turn' }).click()
  await expect(page.locator('.combat-effect').first()).toHaveCSS('animation-name', 'none')
  await page.clock.runFor(250)
  await expect(page.locator('.damage-number').first()).toHaveCSS('animation-name', 'none')
  await expect(page.getByRole('progressbar', { name: 'Bob HP' })).toHaveAttribute(
    'aria-valuenow',
    '92'
  )
})
