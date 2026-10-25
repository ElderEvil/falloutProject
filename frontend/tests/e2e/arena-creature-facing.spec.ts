import { test, expect } from '@playwright/test'

test('creature damage feedback respects reduced motion', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.route('**/static/creature_images/**', (route) => route.abort())
  await page.goto('/tests/e2e/fixtures/arena-ring.html?damage')
  const damage = page.getByText('-15', { exact: true })
  await expect(damage).toHaveCSS('animation-name', 'none')
  await expect(damage.locator('..')).toHaveAttribute('aria-hidden', 'true')
  await page.emulateMedia({ reducedMotion: 'no-preference' })
  await expect(damage).toHaveCSS('animation-name', /damage-float/)
})

for (const { mirror, robot, enemy } of [
  { mirror: false, robot: false, enemy: false },
  { mirror: true, robot: false, enemy: false },
  { mirror: false, robot: true, enemy: true },
  { mirror: false, robot: true, enemy: false },
  { mirror: false, robot: false, enemy: true },
]) {
  test(`creature slot and picker artwork mirror=${mirror}, robot=${robot}, enemy=${enemy}`, async ({
    page,
  }) => {
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
    await page.goto(
      `/tests/e2e/fixtures/arena-creature.html?mirror=${mirror}&robot=${robot}&enemy=${enemy}`
    )
    const images = page.locator('img')
    await expect(images).toHaveCount(2)
    for (const image of await images.all()) {
      await expect(image).toHaveCSS(
        'transform',
        mirror || (robot && enemy) ? 'matrix(-1, 0, 0, 1, 0, 0)' : 'none'
      )
      await expect(image).toHaveAttribute(
        'src',
        robot ? /assembled\/eyebot\.webp/ : /assembled\/radscorpion\.webp/
      )
    }
    await expect(
      page.getByAltText(robot ? 'Training Eyebot' : 'Radscorpion', { exact: true })
    ).toHaveCount(1)
    await expect(page.getByText('20/35 HP', { exact: true })).toBeVisible()
  })
}
