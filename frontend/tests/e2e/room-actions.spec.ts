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
