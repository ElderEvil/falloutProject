import { expect, test } from '@playwright/test'
import { fileURLToPath } from 'node:url'

for (const width of [390, 1280]) {
  test(`journey and encounter frames stay stable while artwork loads at ${width}px`, async ({
    page,
  }) => {
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
    const journey = page.getByRole('figure', { name: "Lucy MacLean's wasteland journey" })
    await expect(journey).toBeVisible()
    const backdrop = journey.getByAltText('Desert highway')
    const before = await backdrop.boundingBox()
    expect(before).not.toBeNull()
    expect(before!.width / before!.height).toBeCloseTo(16 / 9, 2)
    releaseImage()
    await expect
      .poll(() => backdrop.evaluate((image: HTMLImageElement) => image.naturalWidth))
      .toBeGreaterThan(0)
    const after = await backdrop.boundingBox()
    expect(after!.height).toBeCloseTo(before!.height, 1)
    const actor = journey.getByRole('group', { name: 'Lucy MacLean on expedition' })
    const actorBounds = await actor.boundingBox()
    expect(actorBounds!.height / after!.height).toBeCloseTo(0.44, 2)
    const encounter = page.getByRole('figure', { name: 'Encounter backdrop', exact: true })
    const encounterImage = encounter.getByAltText('Desert highway')
    const encounterBounds = await encounterImage.boundingBox()
    expect(encounterBounds!.width / encounterBounds!.height).toBeCloseTo(50 / 37, 2)
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

test('failed artwork keeps the journey caption and explorer visible', async ({ page }) => {
  await page.route('**/assets/wasteland-scenes/**', (route) => route.abort())
  await page.route('**/static/**', (route) => route.abort())
  await page.goto('/tests/e2e/fixtures/wasteland-scenes.html')
  const journey = page.getByRole('figure', { name: "Lucy MacLean's wasteland journey" })
  await expect(journey.getByRole('img', { name: 'Desert highway', exact: true })).toBeVisible()
  await expect(journey.getByRole('group', { name: 'Lucy MacLean on expedition' })).toBeVisible()
  await expect(journey.locator('figcaption')).toContainText('wasteland journey')
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
