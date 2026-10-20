import { expect, test } from '@playwright/test'

for (const theme of ['fo4', 'fo3', 'fnv']) {
  test(`continuous training persists and stays readable in ${theme}`, async ({ page }) => {
    const pageErrors: string[] = []
    page.on('pageerror', (error) => pageErrors.push(error.message))
    if (theme === 'fnv') await page.setViewportSize({ width: 360, height: 800 })
    let enabled = false
    const changes: boolean[] = []
    await page.route('**/api/v1/**', async (route) => {
      if (route.request().url().endsWith('/vaults/vault-1')) {
        if (route.request().method() === 'PUT') {
          enabled = route.request().postDataJSON().continuous_training
          changes.push(enabled)
        }
        return route.fulfill({ json: { id: 'vault-1', number: 1, continuous_training: enabled } })
      }
      return route.fulfill({ json: [] })
    })
    await page.goto(`/tests/e2e/fixtures/continuous-training.html?theme=${theme}`)
    const toggle = page.getByRole('button', { name: 'Continuous training', exact: true })
    await expect(toggle).toHaveAttribute('aria-pressed', 'false')
    await toggle.hover()
    const tooltip = page.locator('[data-slot="tooltip-content"]')
    await expect(tooltip).toContainText('Repeat training rounds until stat 10.')
    await toggle.click()
    await expect(toggle).toHaveAttribute('aria-pressed', 'true')
    expect(changes).toEqual([true])
    const fits = await toggle.evaluate((element) => {
      const bounds = element.closest('.panel-header')!.getBoundingClientRect()
      const button = element.getBoundingClientRect()
      const title = element.closest('.panel-header')!.querySelector('h3')!.getBoundingClientRect()
      return button.left >= title.right && button.right <= bounds.right
    })
    expect(fits).toBe(true)
    await page.reload()
    await expect(toggle).toHaveAttribute('aria-pressed', 'true')
    await toggle.hover()
    await expect(tooltip).toContainText('Click to stop after this round.')
    await page.screenshot({ path: test.info().outputPath(`${theme}-continuous-training.png`) })
    await toggle.click()
    await expect(toggle).toHaveAttribute('aria-pressed', 'false')
    expect(changes).toEqual([true, false])
    expect(pageErrors).toEqual([])
  })
}
