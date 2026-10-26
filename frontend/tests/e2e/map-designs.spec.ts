import { test, expect } from '@playwright/test'
import { fileURLToPath } from 'node:url'

test('illustrated terrain toggles independently and stays below fog', async ({ page }) => {
  await page.route('**/__dev/map-plate.png', (route) =>
    route.fulfill({
      contentType: 'image/webp',
      path: fileURLToPath(
        new URL(
          '../../../backend/app/static/dweller_thumbnails/base/FOS_Dw_Default_Human_Female.webp',
          import.meta.url
        )
      ),
    })
  )
  await page.goto('/tests/e2e/fixtures/map-designs.html')
  const plate = page.locator('.illustrated-plate')
  await expect(plate).toHaveAttribute('opacity', '1')
  await expect(page.locator('.map-grid')).toBeVisible()
  const scale = page.locator('.scale-distance')
  await expect.poll(async () => Number(await scale.innerText())).toBeGreaterThan(0)
  const initialDistance = Number(await scale.innerText())
  await page.getByRole('button', { name: 'Zoom in', exact: true }).click()
  await expect.poll(async () => Number(await scale.innerText())).toBeLessThan(initialDistance)
  await page.getByRole('button', { name: 'Reset zoom', exact: true }).click()
  await page.getByRole('switch', { name: 'Fog of war' }).click()
  expect(
    await plate.evaluate((el) =>
      Boolean(
        el.compareDocumentPosition(document.querySelector('.atlas-fog')!) &
        Node.DOCUMENT_POSITION_FOLLOWING
      )
    )
  ).toBe(true)
  expect(
    await page
      .locator('.map-grid')
      .evaluate((el) =>
        Boolean(
          el.compareDocumentPosition(document.querySelector('.atlas-fog')!) &
          Node.DOCUMENT_POSITION_FOLLOWING
        )
      )
  ).toBe(true)
  await page.getByRole('switch', { name: 'Illustrated terrain' }).click()
  await expect(plate).toHaveCount(0)
  await expect(page.locator('.atlas-terrain image')).toBeVisible()
  await page.getByRole('switch', { name: 'Illustrated terrain' }).click()
  await expect(plate).toHaveAttribute('opacity', '1')
})

test('missing local art falls back to procedural terrain', async ({ page }) => {
  await page.route('**/__dev/map-plate.png', (route) => route.fulfill({ status: 404, body: '' }))
  await page.goto('/tests/e2e/fixtures/map-designs.html')
  await expect(page.getByRole('status')).toContainText('Showing procedural terrain')
  await expect(page.locator('.illustrated-plate')).toHaveCount(0)
  await expect(page.locator('.atlas-terrain image')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Zoom in', exact: true })).toBeVisible()
})

for (const width of [1440, 390]) {
  test(`map designs remain usable at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 })
    await page.goto('/tests/e2e/fixtures/map-designs.html')
    for (const name of ['Regional atlas', 'Field chart', 'Survey terminal']) {
      await page.getByRole('button', { name: new RegExp(name) }).click()
      const preview = page.getByRole('region', { name: `${name} preview` })
      await expect(preview).toBeVisible()
      await expect(preview.locator('.atlas-terrain image')).toHaveAttribute('href', /^data:image/)
      const bounds = await preview.boundingBox()
      expect(bounds!.width).toBeLessThanOrEqual(width)
      const map = await preview.locator('.world-map-container').boundingBox()
      expect(Math.abs(map!.width - map!.height)).toBeLessThan(2)
      if (width >= 1280) {
        const sidebar = await preview.locator('.map-index').boundingBox()
        expect(sidebar!.x).toBeGreaterThanOrEqual(map!.x + map!.width - 1)
        const panel = preview.locator('.map-index .marker-list-panel')
        expect(Math.abs((await panel.boundingBox())!.height - map!.height)).toBeLessThan(2)
        await panel.getByRole('tab', { name: 'Legend', exact: true }).click()
        await expect(panel.getByRole('region', { name: 'Map legend' })).toBeVisible()
        await panel.getByRole('tab', { name: 'Places', exact: true }).click()
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(
        width
      )
      const beforeZoom = await preview.locator('.world-map-svg').getAttribute('viewBox')
      await preview.getByRole('button', { name: 'Zoom in', exact: true }).click()
      await expect(preview.locator('.world-map-svg')).not.toHaveAttribute('viewBox', beforeZoom!)
      await preview.getByRole('button', { name: 'Reset zoom', exact: true }).click()
    }
    await page.getByRole('switch', { name: 'Fog of war' }).click()
    await expect(page.locator('.atlas-fog')).toBeVisible()
    await page.getByRole('switch', { name: 'Fog of war' }).click()
    await expect(page.locator('.atlas-fog')).toHaveCount(0)
    await page.getByRole('button', { name: /Regional atlas/ }).click()
    await page
      .getByRole('button', { name: /Red Rocket \(/ })
      .first()
      .click()
    await expect(page.getByRole('region', { name: 'Selected place' })).toContainText('Red Rocket')
  })
}
