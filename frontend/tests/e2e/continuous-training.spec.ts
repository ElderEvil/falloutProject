import { expect, test } from '@playwright/test'

for (const theme of ['fo4', 'fo3', 'fnv']) {
  test(`continuous training persists and stays readable in ${theme}`, async ({ page }) => {
    const pageErrors: string[] = []
    page.on('pageerror', (error) => pageErrors.push(error.message))
    if (theme === 'fnv') await page.setViewportSize({ width: 360, height: 800 })
    let enabled = false
    const changes: boolean[] = []
    const sessions = [
      ['later', 120, 'r1'],
      ['soon', 5, 'r2'],
      ['first', 1, 'r1'],
    ].map(([id, minutes, roomId]) => ({
      id,
      dweller_id: id,
      room_id: roomId,
      stat_being_trained: 'strength',
      status: 'active',
      current_stat_value: 5,
      target_stat_value: 6,
      goal_stat_value: 10,
      progress: 0,
      started_at: new Date(Date.now() - 60_000).toISOString(),
      estimated_completion_at: new Date(Date.now() + Number(minutes) * 60_000).toISOString(),
    }))
    await page.route('**/api/v1/**', async (route) => {
      if (route.request().url().endsWith('/vaults/vault-1')) {
        if (route.request().method() === 'PUT') {
          enabled = route.request().postDataJSON().continuous_training
          changes.push(enabled)
        }
        return route.fulfill({ json: { id: 'vault-1', number: 1, continuous_training: enabled } })
      }
      if (route.request().url().endsWith('/goal')) {
        const id = route.request().url().split('/').at(-2)
        const session = sessions.find((item) => item.id === id)!
        session.goal_stat_value = route.request().postDataJSON().goal_stat_value
        return route.fulfill({ json: session })
      }
      if (route.request().url().includes('/training/vault/'))
        return route.fulfill({ json: sessions })
      if (route.request().url().includes('/dwellers/'))
        return route.fulfill({
          json: sessions.map((session) => ({
            id: session.id,
            first_name: session.id === 'first' ? 'Alice' : session.id === 'soon' ? 'Bob' : 'Carol',
            last_name: 'Vault',
            room_id: session.room_id,
            status: 'training',
            level: 1,
          })),
        })
      if (route.request().url().includes('/rooms/vault/'))
        return route.fulfill({
          json: [
            { id: 'r1', name: 'Weight Room' },
            { id: 'r2', name: 'Fitness Room' },
          ],
        })
      return route.fulfill({ json: [] })
    })
    await page.goto(`/tests/e2e/fixtures/continuous-training.html?theme=${theme}`)
    const toggle = page.getByRole('button', { name: 'Repeat training', exact: true })
    await expect(toggle).toHaveText('Repeat training')
    await expect(toggle).toHaveAttribute('aria-pressed', 'false')
    await toggle.hover()
    const tooltip = page.locator('[data-slot="tooltip-content"]')
    await expect(tooltip).toContainText('Repeat training rounds to each dweller’s goal.')
    await toggle.click()
    await expect(toggle).toHaveAttribute('aria-pressed', 'true')
    expect(changes).toEqual([true])
    const fits = await toggle.evaluate((element) => {
      const bounds = element.closest('.panel-header')!.getBoundingClientRect()
      const button = element.getBoundingClientRect()
      const title = element.closest('.panel-header')!.querySelector('h3')!.getBoundingClientRect()
      return (
        (button.left >= title.right || button.top >= title.bottom) && button.right <= bounds.right
      )
    })
    expect(fits).toBe(true)
    await page.reload()
    await expect(toggle).toHaveAttribute('aria-pressed', 'true')
    const cards = page.locator('.training-progress-card')
    await expect(cards).toHaveCount(3)
    await expect(cards.nth(0)).toContainText('Alice Vault')
    await expect(cards.nth(1)).toContainText('Carol Vault')
    await expect(cards.nth(2)).toContainText('Bob Vault')
    await expect(cards.nth(0)).toContainText('Strength 5 → 6')
    const aliceGoal = page.getByRole('combobox', { name: 'Training goal for Alice Vault' })
    await expect(aliceGoal).toContainText('10')
    await aliceGoal.click()
    await page.getByRole('option', { name: '7', exact: true }).click()
    await expect(aliceGoal).toContainText('7')
    await page.reload()
    await expect(aliceGoal).toContainText('7')
    await expect(page.getByRole('combobox', { name: 'Training goal for Bob Vault' })).toContainText(
      '10'
    )
    await expect(
      page.getByRole('region', { name: 'Weight Room' }).locator('.training-progress-card')
    ).toHaveCount(2)
    await expect(
      page.getByRole('region', { name: 'Fitness Room' }).locator('.training-progress-card')
    ).toHaveCount(1)
    await expect(cards.nth(0)).toContainText('Soon')
    const rowsFit = await cards.evaluateAll((rows) =>
      rows.every((row) => row.scrollWidth <= row.clientWidth)
    )
    expect(rowsFit).toBe(true)
    await toggle.hover()
    await expect(tooltip).toContainText('Click to stop after this round.')
    await page.screenshot({ path: test.info().outputPath(`${theme}-continuous-training.png`) })
    await toggle.click()
    await expect(toggle).toHaveAttribute('aria-pressed', 'false')
    expect(changes).toEqual([true, false])
    expect(pageErrors).toEqual([])
  })
}
