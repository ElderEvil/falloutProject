import { test, expect } from '@playwright/test'

for (const theme of ['fo4', 'fo3', 'fnv']) {
  for (const surface of ['canvas', 'surface', 'raised']) {
    test(`briefing alert contrast: ${theme} / ${surface}`, async ({ page }) => {
      await page.goto(
        `/tests/e2e/fixtures/overseer-briefing.html?theme=${theme}&surface=${surface}`
      )
      for (const text of [
        'RESPONSE REQUIRED',
        'WATCH LIST ACTIVE',
        '1 INCIDENT REQUIRES RESPONSE',
        'DWELLER MORALE NEEDS ATTENTION (30%)',
      ]) {
        const label = page.getByText(text, { exact: true })
        await expect(label).toBeVisible()
        const contrast = await label.evaluate((element) => {
          // Canvas normalizes browser-computed rgb/oklab/color-mix values to sRGB.
          const context = document.createElement('canvas').getContext('2d')!
          const rgba = (color: string) => {
            context.clearRect(0, 0, 1, 1)
            context.fillStyle = color
            context.fillRect(0, 0, 1, 1)
            const value = Array.from(context.getImageData(0, 0, 1, 1).data)
            value[3] /= 255
            return value
          }
          const blend = (foreground: number[], background: number[]) =>
            foreground
              .slice(0, 3)
              .map((value, i) => value * foreground[3] + background[i] * (1 - foreground[3]))
          const luminance = (rgb: number[]) =>
            rgb
              .map((value) => value / 255)
              .map((value) => (value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4))
              .reduce((sum, value, i) => sum + value * [0.2126, 0.7152, 0.0722][i], 0)

          const ancestors: Element[] = []
          for (let node: Element | null = element; node; node = node.parentElement)
            ancestors.unshift(node)
          const background = ancestors.reduce(
            (color, node) => blend(rgba(getComputedStyle(node).backgroundColor), color),
            [255, 255, 255]
          )
          const style = getComputedStyle(element)
          const foreground = rgba(style.color)
          foreground[3] *= Number(style.opacity)
          const light = luminance(blend(foreground, background))
          const dark = luminance(background)
          return (Math.max(light, dark) + 0.05) / (Math.min(light, dark) + 0.05)
        })
        expect(contrast, `${text}: ${contrast.toFixed(2)}:1`).toBeGreaterThanOrEqual(4.5)
      }
    })
  }
}
