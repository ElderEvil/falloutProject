import { test, expect } from '@playwright/test'

// Regression net for the upcoming shadcn-vue swap of the core UI primitives.
// The catalog view imports stay pinned to @/core/components/ui, so these
// baselines prove the swap is visually neutral. Overlay states are made
// deterministic in the spec: the tooltip trigger is focused (never hovered)
// and the modal/toasts are rendered open by the catalog itself.
test.use({ reducedMotion: 'reduce' })

test.describe('UI catalog', () => {
  test('renders every primitive and matches the baseline', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 })
    await page.goto('/dev/ui-catalog')
    await expect(page.getByRole('heading', { name: 'UI Catalog' })).toBeVisible({ timeout: 10000 })

    // Deterministic overlay state: focus (not hover) the tooltip trigger so the
    // teleported tooltip is visible for both the aria snapshot and the screenshot.
    await page.getByRole('button', { name: 'Tooltip top' }).focus()
    await expect(page.getByRole('tooltip')).toBeVisible()

    await expect(page).toMatchAriaSnapshot()
    await expect(page).toHaveScreenshot('ui-catalog.png', {
      animations: 'disabled',
      fullPage: true,
    })
  })
})