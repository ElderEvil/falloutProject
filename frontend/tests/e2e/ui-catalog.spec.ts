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
})
