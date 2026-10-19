import { test, expect } from '@playwright/test'

for (const theme of ['fo4', 'fo3', 'fnv']) {
  test(`upgrade cost fits a narrow button and follows the ${theme} theme`, async ({ page }) => {
    await page.goto(`/tests/e2e/fixtures/room-actions.html?theme=${theme}`)
    const button = page.getByRole('button', { name: 'Upgrade to Tier 3 180000 caps' })
    await expect(button).toBeVisible()
    const fits = await button.evaluate((element) => {
      const bounds = element.getBoundingClientRect()
      return (
        Array.from(element.querySelectorAll('span')).every((child) => {
          const rect = child.getBoundingClientRect()
          return (
            rect.left >= bounds.left && rect.right <= bounds.right && rect.bottom <= bounds.bottom
          )
        }) && element.scrollWidth <= element.clientWidth
      )
    })
    expect(fits).toBe(true)
    const primary = await button.evaluate((element) => getComputedStyle(element).color)
    await expect(button.locator('.cost-badge')).toHaveCSS('color', primary)
    await button.click()
    await expect(page.locator('output')).toHaveText('Upgrade requested')
    await expect(button).toBeDisabled()
  })
}

test('remodel actions stay in one equally sized row and keep the upgrade cost inside its button', async ({
  page,
}) => {
  await page.goto('/tests/e2e/fixtures/room-actions.html?remodel=1')
  const actions = page.locator('.actions-grid')
  const buttons = actions.getByRole('button')
  const upgrade = actions.getByRole('button', { name: 'Upgrade to Tier 3 180000 caps' })
  await expect(buttons).toHaveCount(4)
  await page.locator('#app').evaluate((el) => (el.style.width = '600px'))
  const wideLayout = await buttons.evaluateAll((elements) => {
    const rects = elements.map((element) => element.getBoundingClientRect())
    return {
      widths: rects.map((rect) => rect.width),
      tops: rects.map((rect) => rect.top),
    }
  })
  expect(new Set(wideLayout.tops).size).toBe(1)
  expect(Math.max(...wideLayout.widths) - Math.min(...wideLayout.widths)).toBeLessThan(1)
  await page.locator('#app').evaluate((el) => (el.style.width = '200px'))
  const narrowLayout = await buttons.evaluateAll((elements) => {
    const rects = elements.map((element) => element.getBoundingClientRect())
    return { widths: rects.map((rect) => rect.width), tops: rects.map((rect) => rect.top) }
  })
  expect(new Set(narrowLayout.tops).size).toBe(1)
  expect(Math.max(...narrowLayout.widths) - Math.min(...narrowLayout.widths)).toBeLessThan(1)
  const badge = upgrade.locator('.cost-badge')
  const badgePosition = await badge.evaluate((el) => {
    const parent = el.closest('button')!.getBoundingClientRect()
    const box = el.getBoundingClientRect()
    return {
      contained:
        box.left >= parent.left && box.right <= parent.right && box.bottom <= parent.bottom,
      top: box.top,
    }
  })
  expect(badgePosition.contained).toBe(true)
  const titleTop = await upgrade
    .locator('span')
    .first()
    .evaluate((el) => el.getBoundingClientRect().top)
  expect(badgePosition.top).toBeGreaterThan(titleTop)
})
