import { test, expect } from '@playwright/test'

// Regression net for the core UI primitives. The catalog renders every primitive
// in all its variants and states, with overlays (dialog, tooltips, toasts)
// rendered open by the catalog itself, so the aria snapshot and pixel screenshot
// capture a deterministic page.
test.use({ reducedMotion: 'reduce' })

test.describe('UI catalog', () => {
  test('renders every primitive and matches the baseline', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 })
    await page.goto('/dev/ui-catalog')
    await expect(page.getByRole('heading', { name: 'UI Catalog' })).toBeVisible({ timeout: 10000 })

    await expect(page).toMatchAriaSnapshot()
    await expect(page).toHaveScreenshot('ui-catalog.png', {
      animations: 'disabled',
      fullPage: true,
      timeout: 20000,
    })
  })

  // A `fill` may be a gradient; the indicator must apply it as a background image,
  // not as `background-color` (which drops a gradient and renders no fill at all).
  test('renders a gradient fill as a background image', async ({ page }) => {
    await page.goto('/dev/ui-catalog')
    await expect(page.getByRole('heading', { name: 'UI Catalog' })).toBeVisible({ timeout: 10000 })

    const indicator = page.locator('[aria-label="Gradient fill"] [data-slot="progress-indicator"]')
    await expect(indicator).toHaveCSS('background-image', /linear-gradient/)
  })
})
