import { test, expect } from '@playwright/test'

for (const width of [390, 1280]) {
  for (const reducedMotion of ['no-preference', 'reduce'] as const) {
    test(`reveals in place at ${width}px with ${reducedMotion} motion`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 })
      await page.emulateMedia({ reducedMotion })
      await page.goto('/tests/e2e/fixtures/lunchbox-reveal.html')
      const dialog = page.getByRole('dialog')
      const slots = dialog.locator('[data-reward-slot]')
      await expect(slots).toHaveCount(4)
      await expect(page.getByRole('button', { name: 'Reveal Contents' })).toBeVisible()
      // Let the dialog enter before freezing time for the card sequence.
      await page.waitForTimeout(350)
      await page.clock.install()
      await page.clock.pauseAt(new Date())
      const bounds = await slots.evaluateAll((elements) =>
        elements.map((element) => {
          const { x, y, width, height } = element.getBoundingClientRect()
          return { x, y, width, height }
        })
      )
      await page.getByRole('button', { name: 'Reveal Contents' }).click()
      const names = ['Laser Pistol', 'Vault Suit', 'Heavy wasteland gear', 'Lucy MacLean']
      for (let index = 0; index < names.length; index++) {
        await page.clock.runFor(index === 0 ? 1 : 900)
        await expect(slots.nth(index)).toContainText(names[index]!)
        if (index < names.length - 1) {
          await expect(slots.nth(index + 1)).not.toContainText(names[index + 1]!)
        }
      }
      await page.clock.runFor(750)
      await expect(page.getByRole('button', { name: 'Done' })).toBeEnabled()
      expect(
        await slots.evaluateAll((elements) =>
          elements.map((element) => {
            const { x, y, width, height } = element.getBoundingClientRect()
            return { x, y, width, height }
          })
        )
      ).toEqual(bounds)
      expect(await dialog.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(
        true
      )
      const frames = await slots
        .last()
        .locator('[data-slot="card"]')
        .evaluate((element) =>
          element
            .getAnimations()
            .flatMap((animation) =>
              animation.effect instanceof KeyframeEffect ? animation.effect.getKeyframes() : []
            )
        )
      expect(frames.some((frame) => String(frame.transform).includes('scale(1.08)'))).toBe(
        reducedMotion !== 'reduce'
      )
    })
  }
}
