import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.clock.install()
  await page.clock.pauseAt(new Date())
  await page.goto('/tests/e2e/fixtures/combat-zone.html', { waitUntil: 'domcontentloaded' })
  await expect(
    page.getByRole('region', { name: 'Interchange 77 regulation bout' }).first()
  ).toBeVisible()
})

for (const width of [390, 1280]) {
  test(`Combat Zone live playback and result at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 1100 })
    await page.clock.runFor(900)

    await expect(page.locator('#live-bout').getByText('Bout in progress')).toBeVisible()
    await expect(
      page.locator('#replay-bout').getByRole('progressbar', { name: 'Bob HP' })
    ).toHaveAttribute('aria-valuenow', '88')
    await expect(page.locator('#replay-bout').getByText('88 / 100 HP')).toBeVisible()

    await page.locator('#finish-live').click()
    await expect(page.locator('#live-bout').getByRole('heading', { name: 'Victory' })).toBeVisible()

    await page.locator('#open-result').click()
    await expect(page.getByRole('dialog').getByRole('heading', { name: 'Victory' })).toBeVisible()
    await expect(page.getByRole('dialog').getByText(/Purse/)).toBeVisible()
    await expect(
      page
        .getByRole('dialog')
        .getByText(/caps credited/)
        .first()
    ).toBeVisible()
    await expect(page.getByRole('dialog').getByText('The signal is dark.')).toHaveCount(0)

    await page.screenshot({
      path: testInfo.outputPath(`combat-zone-${width}.png`),
      fullPage: true,
    })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })
}

test('reduced motion keeps the bout readable', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.clock.runFor(900)

  const live = page.locator('#live-bout')
  await expect(live.getByText('Bout in progress')).toBeVisible()
  await expect(live.getByText('Alice').first()).toBeVisible()
  await expect(live.getByText('Bob').first()).toBeVisible()
  await page.locator('#open-result').click()
  await expect(page.getByRole('dialog').getByRole('heading', { name: 'Victory' })).toBeVisible()
})
