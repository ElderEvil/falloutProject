import { test, expect } from '@playwright/test'

test('small rooms use a header stat cue instead of stacking text over the room', async ({
  page,
}) => {
  await page.goto('/tests/e2e/fixtures/room-drag.html')
  for (const size of [3, 6]) {
    const room = page.locator(`[data-size="${size}"] .built-room`)
    const stat = room.locator('.drag-ability-letter')
    await expect(stat).toBeVisible()
    await expect(stat).toHaveText('S')
    await expect(room.locator('.drop-indicator')).toBeHidden()
    const fits = await stat.evaluate((element) => {
      const bounds = element.closest('.room-info-overlay')!.getBoundingClientRect()
      const box = element.getBoundingClientRect()
      const name = element
        .closest('.room-header')!
        .querySelector('.room-name')!
        .getBoundingClientRect()
      return (
        box.left >= name.right &&
        box.right <= bounds.right &&
        box.top >= bounds.top &&
        box.bottom <= bounds.bottom
      )
    })
    expect(fits).toBe(true)
  }
  const wide = page.locator('[data-size="9"] .built-room')
  await expect(wide.locator('.drop-indicator')).toBeVisible()
  await expect(wide.locator('.drop-ability')).toHaveText('S · Strength')
  await page.screenshot({ path: test.info().outputPath('room-drag-sizes.png') })
})

test('reduced motion keeps the stat cue without a scaling transition', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/tests/e2e/fixtures/room-drag.html')
  const icon = page.locator('[data-size="9"] .ability-icon')
  await expect(icon).toHaveCSS('transition-duration', '0s')
  await expect(icon).toHaveCSS('transform', 'none')
})
