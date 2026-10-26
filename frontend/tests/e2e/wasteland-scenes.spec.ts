import { expect, test } from '@playwright/test'
import { fileURLToPath } from 'node:url'

for (const [width, height] of [
  [1280, 720],
  [1280, 600],
  [1920, 1080],
  [390, 844],
  [844, 390],
]) {
  test(`combat fits its modal with a long journal at ${width}x${height}`, async ({ page }) => {
    await page.setViewportSize({ width, height })
    await page.goto('/tests/e2e/fixtures/wasteland-scenes.html')
    await page.getByRole('button', { name: 'Preview combat layout', exact: true }).click()
    const dialog = page.getByRole('dialog')
    const scene = dialog.getByRole('region', { name: 'Desert highway', exact: true })
    await expect(scene).toBeVisible()
    await page.waitForTimeout(150)
    const bounds = (await scene.boundingBox())!
    const space = (await dialog.getByLabel('Battlefield space').boundingBox())!
    const footer = (await dialog
      .getByRole('button', { name: 'Close', exact: true })
      .first()
      .boundingBox())!
    expect(bounds.width).toBeGreaterThan(80)
    expect(bounds.height).toBeGreaterThan(60)
    expect(bounds.x).toBeGreaterThanOrEqual(space.x - 1)
    expect(bounds.y).toBeGreaterThanOrEqual(space.y - 1)
    expect(bounds.x + bounds.width).toBeLessThanOrEqual(space.x + space.width + 1)
    expect(bounds.y + bounds.height).toBeLessThanOrEqual(space.y + space.height + 1)
    expect(bounds.y + bounds.height).toBeLessThanOrEqual(footer.y)
    for (const actor of await scene.locator('.ring-fighter').all()) {
      const actorBounds = (await actor.boundingBox())!
      expect(actorBounds.y).toBeGreaterThanOrEqual(bounds.y + 28)
      expect(actorBounds.y + actorBounds.height).toBeLessThanOrEqual(bounds.y + bounds.height)
    }
    const log = dialog.getByLabel('Battle log', { exact: true })
    await expect(log).toContainText('SKILL')
    await expect(log).toContainText('Turn 1')
    await expect(log).toContainText('Turn 30')
    expect(await log.evaluate((el) => el.scrollHeight > el.clientHeight)).toBe(true)
    expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false)
    await page.screenshot({ path: `test-results/site-combat-fit-${width}-${height}.png` })
  })
}

for (const glow of ['off', 'subtle', 'normal', 'strong']) {
  test(`briefing titles respect ${glow} glow and remain unclipped`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.addInitScript((glow) => localStorage.setItem('visual-effects:glow', glow), glow)
    await page.goto('/tests/e2e/fixtures/wasteland-scenes.html')
    await page.getByRole('combobox', { name: 'Preview location' }).click()
    await page.getByRole('option', { name: 'Arctic research station', exact: true }).click()
    await page.getByRole('button', { name: 'Preview briefing', exact: true }).click()
    const dialog = page.getByRole('dialog')
    const title = dialog.getByRole('heading', { name: 'Arctic research station', exact: true })
    if (glow === 'off') {
      await expect(title).toHaveCSS('text-shadow', 'none')
      await expect(dialog).not.toHaveCSS('box-shadow', /20px/)
    } else {
      await expect(title).not.toHaveCSS('text-shadow', 'none')
    }
    await expect(title).toHaveCSS('overflow', 'visible')
    const bounds = (await title.boundingBox())!
    const frame = (await dialog.boundingBox())!
    expect(bounds.x - frame.x).toBeGreaterThan(20)
    expect(bounds.y - frame.y).toBeGreaterThan(20)
    expect(bounds.x + bounds.width).toBeLessThan(frame.x + frame.width - 20)
    // Same-document preference changes must also reach the teleported header.
    await page.evaluate(() => {
      localStorage.setItem('visual-effects:glow', 'off')
      window.dispatchEvent(
        new StorageEvent('storage', {
          key: 'visual-effects:glow',
          newValue: 'off',
          storageArea: localStorage,
        })
      )
    })
    await expect(title).toHaveCSS('text-shadow', 'none')
    await page.getByRole('button', { name: 'Close briefing', exact: true }).click()
    await expect(dialog).toHaveCount(0)
  })
}

for (const width of [390, 1280]) {
  test(`the encounter scene stays stable while artwork loads at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.route('**/static/**', (route) =>
      route.fulfill({
        path: fileURLToPath(
          new URL(
            '../../../backend/app/static/dweller_thumbnails/base/FOS_Dw_Default_Human_Female.webp',
            import.meta.url
          )
        ),
      })
    )
    let releaseImage: () => void = () => {}
    const imageGate = new Promise<void>((resolve) => {
      releaseImage = resolve
    })
    await page.route('**/assets/wasteland-scenes/**', async (route) => {
      await imageGate
      await route.continue()
    })
    await page.goto('/tests/e2e/fixtures/wasteland-scenes.html', { waitUntil: 'domcontentloaded' })
    const journey = page.getByRole('figure', { name: 'Encounter scene', exact: true })
    await expect(journey).toBeVisible()
    const backdrop = journey.getByAltText('Desert highway')
    const before = await backdrop.boundingBox()
    expect(before).not.toBeNull()
    expect(before!.width / before!.height).toBeCloseTo(50 / 37, 2)
    releaseImage()
    await expect
      .poll(() => backdrop.evaluate((image: HTMLImageElement) => image.naturalWidth))
      .toBeGreaterThan(0)
    const after = await backdrop.boundingBox()
    expect(after!.height).toBeCloseTo(before!.height, 1)
    const actor = journey.getByRole('group', { name: 'Lucy MacLean on expedition' })
    const actorBounds = await actor.boundingBox()
    expect(actorBounds!.height / after!.height).toBeCloseTo(0.44, 2)
    await page.getByRole('combobox', { name: 'Preview location' }).click()
    await page.getByRole('option', { name: 'Subway station', exact: true }).click()
    await expect(journey.getByAltText('Subway station')).toBeVisible()
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth
    )
    expect(overflow).toBe(false)
    await page.screenshot({ path: `test-results/wasteland-scenes-${width}.png`, fullPage: true })
  })
}

test('failed artwork keeps the encounter caption and explorer visible', async ({ page }) => {
  await page.route('**/assets/wasteland-scenes/**', (route) => route.abort())
  await page.route('**/static/**', (route) => route.abort())
  await page.goto('/tests/e2e/fixtures/wasteland-scenes.html')
  const journey = page.getByRole('figure', { name: 'Encounter scene', exact: true })
  await expect(journey.getByRole('img', { name: 'Desert highway', exact: true })).toBeVisible()
  await expect(journey.getByRole('group', { name: 'Lucy MacLean on expedition' })).toBeVisible()
  await expect(journey.locator('figcaption')).toContainText('Encounter scene')
})

test('the development menu links to the scene preview', async ({ page }) => {
  await page.route('**/api/v1/**', (route) => route.fulfill({ json: {} }))
  await page.route('**/static/**', (route) => route.abort())
  await page.goto('/dev')
  const previewLink = page.getByRole('link', { name: /Wasteland scenes/ })
  await expect(previewLink).toHaveAttribute('href', '/dev/wasteland-scenes')
  await previewLink.click()
  await expect(page.getByRole('heading', { name: 'Wasteland scenes', exact: true })).toBeVisible()
  await expect(page.getByRole('combobox', { name: 'Preview location' })).toBeVisible()
})
