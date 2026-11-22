import { test, expect } from '@playwright/test'

/**
 * The explorer card's dweller link renders the name and a small "open dweller"
 * arrow. When the name wraps, the arrow must follow the last line; a flex row
 * centres it beside the whole block and strands it between the two lines.
 */
test('the dweller link icon follows the last wrapped name line', async ({ page }) => {
  await page.goto('/tests/e2e/fixtures/explorer-card-name.html')
  await page.waitForSelector('.explorer-card .dweller-link-icon')

  const geometry = await page.evaluate(() => {
    const name = document.querySelector('.dweller-name')!
    const icon = document.querySelector('.dweller-link-icon')!
    const range = document.createRange()
    range.selectNodeContents(name)
    const lines = [...range.getClientRects()].map((rect) => ({
      top: rect.top,
      right: rect.right,
      bottom: rect.bottom,
    }))
    const iconRect = icon.getBoundingClientRect()
    return { lines, icon: { top: iconRect.top, left: iconRect.left } }
  })

  expect(geometry.lines.length).toBeGreaterThan(1)
  const lastLine = geometry.lines.at(-1)!
  expect(geometry.icon.top).toBeGreaterThanOrEqual(lastLine.top - 1)
  expect(geometry.icon.top).toBeLessThan(lastLine.bottom)
  expect(geometry.icon.left).toBeGreaterThanOrEqual(lastLine.right)
})
