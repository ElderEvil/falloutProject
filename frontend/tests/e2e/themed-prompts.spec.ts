import { expect, test } from '@playwright/test'

for (const [theme, color] of [
  ['fo4', 'rgb(0, 255, 0)'],
  ['fo3', 'rgb(0, 255, 159)'],
  ['fnv', 'rgb(255, 183, 0)'],
]) {
  test(`dweller tooltips and confirmations follow the ${theme} palette`, async ({ page }) => {
    const nativeDialogs: string[] = []
    page.on('dialog', async (dialog) => {
      nativeDialogs.push(dialog.message())
      await dialog.dismiss()
    })
    let mutations = 0
    await page.route('**/api/v1/relationships/vault/vault-1', (route) =>
      route.fulfill({
        json: [
          {
            id: 'r1',
            dweller_1_id: 'd1',
            dweller_2_id: 'd2',
            relationship_type: 'partner',
            affinity: 80,
          },
        ],
      })
    )
    await page.route('**/api/v1/rooms/split/room-1', (route) => {
      mutations++
      return route.fulfill({ json: [] })
    })
    await page.route('**/api/v1/relationships/r1', (route) => {
      mutations++
      return route.fulfill({ status: 204 })
    })
    await page.goto(`/tests/e2e/fixtures/themed-prompts.html?theme=${theme}`)
    await page.locator('.dweller-avatar').first().hover()
    const tooltip = page
      .locator('[data-slot="tooltip-content"]')
      .filter({ hasText: 'Alice Smith (Lv3)' })
    await expect(tooltip).toBeVisible()
    await expect(tooltip).toHaveCSS('color', color)
    await expect(page.locator('.dweller-avatar').first()).not.toHaveAttribute('title')
    await page.getByRole('button', { name: 'Split room', exact: true }).click()
    const dialog = page.getByRole('dialog')
    await expect(dialog).toHaveAccessibleName('Split Living Room?')
    await expect(dialog.getByRole('heading')).toHaveCSS('color', color)
    await page.keyboard.press('Escape')
    await expect(dialog).toBeHidden()
    expect(mutations).toBe(0)
    await page.getByRole('button', { name: 'Split room', exact: true }).click()
    await dialog.getByRole('button', { name: 'Split room', exact: true }).click()
    await expect.poll(() => mutations).toBe(1)
    await page.getByRole('button', { name: 'Break Up', exact: true }).click()
    await expect(dialog).toHaveAccessibleName('End relationship?')
    await expect(dialog.getByRole('heading')).toHaveCSS('color', color)
    await dialog.getByRole('button', { name: 'Cancel', exact: true }).click()
    await expect(dialog).toBeHidden()
    expect(mutations).toBe(1)
    await page.getByRole('button', { name: 'Break Up', exact: true }).click()
    await page.screenshot({ path: test.info().outputPath(`${theme}-confirmation.png`) })
    await dialog.getByRole('button', { name: 'End relationship', exact: true }).click()
    await expect.poll(() => mutations).toBe(2)
    expect(nativeDialogs).toEqual([])
  })
}
