import { test, expect } from '@playwright/test'

for (const mirror of [false, true]) {
  test(`creature slot and picker artwork mirror=${mirror}`, async ({ page }) => {
    // Keep the component's image-error fallback inactive without needing a backend.
    await page.route('**/static/creature_images/**', (route) =>
      route.fulfill({
        contentType: 'image/png',
        body: Buffer.from(
          'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=',
          'base64'
        ),
      })
    )
    await page.goto(`/tests/e2e/fixtures/arena-creature.html?mirror=${mirror}`)
    const images = page.locator('img')
    await expect(images).toHaveCount(2)
    for (const image of await images.all()) {
      await expect(image).toHaveCSS('transform', mirror ? 'matrix(-1, 0, 0, 1, 0, 0)' : 'none')
      await expect(image).toHaveAttribute('src', /assembled\/radscorpion\.webp/)
    }
    await expect(page.getByAltText('Radscorpion', { exact: true })).toHaveCount(1)
    await expect(page.getByText('20/35', { exact: true })).toBeVisible()
  })
}
