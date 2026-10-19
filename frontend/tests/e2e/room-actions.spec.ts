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

test('remodel actions keep content-sized buttons and the upgrade cost inside its button', async ({
  page,
}) => {
  await page.goto('/tests/e2e/fixtures/room-actions.html?remodel=1')
  const actions = page.locator('.actions-grid')
  const split = actions.getByRole('button', { name: 'Split into 2 rooms' })
  const destroy = actions.getByRole('button', { name: 'Destroy Room' })
  const upgrade = actions.getByRole('button', { name: 'Upgrade to Tier 3 180000 caps' })
  await expect(split).toBeVisible()
  await expect(destroy).toBeVisible()
  await page.locator('#app').evaluate((el) => (el.style.width = '600px'))
  const widths = await Promise.all(
    [split, destroy].map((button) => button.evaluate((el) => el.getBoundingClientRect().width))
  )
  expect(widths[0]).toBeLessThan(200)
  expect(widths[1]).toBeLessThan(160)
  await page.locator('#app').evaluate((el) => (el.style.width = '200px'))
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
