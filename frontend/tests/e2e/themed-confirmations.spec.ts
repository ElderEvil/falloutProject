import { expect, test } from '@playwright/test'

for (const [theme, color] of [
  ['fo4', 'rgb(0, 255, 0)'],
  ['fo3', 'rgb(0, 255, 159)'],
  ['fnv', 'rgb(255, 183, 0)'],
]) {
  test(`confirmations use the ${theme} palette and require approval`, async ({ page }) => {
    const nativeDialogs: string[] = []
    const pageErrors: string[] = []
    page.on('dialog', async (dialog) => {
      nativeDialogs.push(dialog.message())
      await dialog.dismiss()
    })
    page.on('pageerror', (error) => pageErrors.push(error.message))
    let mutations = 0
    await page.route('**/api/v1/**', async (route) => {
      const url = route.request().url()
      if (url.endsWith('/relationships/vault/vault-1'))
        return route.fulfill({
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
      if (route.request().method() !== 'GET') {
        mutations++
        return route.fulfill({ json: [] })
      }
      if (url.endsWith('/vaults/vault-1'))
        return route.fulfill({ json: { id: 'vault-1', number: 1 } })
      return route.fulfill({ json: [] })
    })
    await page.goto(`/tests/e2e/fixtures/themed-confirmations.html?theme=${theme}`)
    const dialog = page.getByRole('dialog')
    for (const [request, title, approve] of [
      ['Destroy test room', 'Destroy Living Room?', 'Destroy room'],
      ['Split room', 'Split Living Room?', 'Split room'],
      ['Break Up', 'End relationship?', 'End relationship'],
    ]) {
      const before = mutations
      await page.getByRole('button', { name: request, exact: true }).click()
      await expect(dialog).toHaveAccessibleName(title)
      await expect(dialog.getByRole('heading')).toHaveCSS('color', color)
      await dialog.getByRole('button', { name: 'Cancel', exact: true }).click()
      await expect(dialog).toBeHidden()
      expect(mutations).toBe(before)
      await page.getByRole('button', { name: request, exact: true }).click()
      await page.keyboard.press('Escape')
      await expect(dialog).toBeHidden()
      expect(mutations).toBe(before)
      await page.getByRole('button', { name: request, exact: true }).click()
      await dialog.getByRole('button', { name: approve, exact: true }).click()
      await expect.poll(() => mutations).toBe(before + 1)
    }
    expect(nativeDialogs).toEqual([])
    expect(pageErrors).toEqual([])
  })
}

for (const [theme, color] of [
  ['fo4', 'rgb(0, 255, 0)'],
  ['fo3', 'rgb(0, 255, 159)'],
  ['fnv', 'rgb(255, 183, 0)'],
]) {
  for (const [flow, request, title, approve, expected] of [
    ['vault', 'Delete Vault', 'Delete vault?', 'Delete vault', 1],
    ['craft', 'Cancel', 'Cancel Pipe pistol?', 'Cancel crafting', 1],
    ['unassign', 'Unassign All Dwellers', 'Unassign dwellers?', 'Unassign all', 2],
  ] as const) {
    test(`${flow} confirmation uses ${theme} and keeps cancellation safe`, async ({ page }) => {
      let mutations = 0
      const nativeDialogs: string[] = []
      const errors: string[] = []
      page.on('dialog', async (dialog) => {
        nativeDialogs.push(dialog.message())
        await dialog.dismiss()
      })
      page.on('pageerror', (error) => errors.push(error.message))
      const vault = {
        id: 'vault-1',
        number: 101,
        bottle_caps: 1000,
        happiness: 75,
        power: 50,
        power_max: 100,
        food: 50,
        food_max: 100,
        water: 50,
        water_max: 100,
        dweller_count: 2,
        room_count: 1,
        updated_at: new Date().toISOString(),
      }
      const order = {
        id: 'order-1',
        room_id: 'room-1',
        item_name: 'Pipe pistol',
        item_type: 'weapon',
        rarity: 'common',
        status: 'active',
        progress: 0,
        started_at: new Date().toISOString(),
        estimated_completion_at: new Date(Date.now() + 60_000).toISOString(),
        junk_spent: 3,
        caps_spent: 0,
        required_stat: 'agility',
        ability_sum_at_start: 0,
      }
      await page.route('**/api/v1/**', async (route) => {
        const url = route.request().url()
        if (route.request().method() !== 'GET') {
          mutations++
          if (flow === 'unassign')
            return route.fulfill({
              json: {
                id: url.split('/').at(-1),
                first_name: 'Dweller',
                last_name: '',
                room_id: null,
                level: 1,
                status: 'idle',
              },
            })
          return route.fulfill({ json: { ...order, status: 'cancelled' } })
        }
        if (url.includes('/vaults/'))
          return route.fulfill({
            json: new URL(url).pathname.endsWith('/vaults/my') ? [vault] : vault,
          })
        if (url.includes('/recipes/')) return route.fulfill({ json: { recipes: [] } })
        if (url.endsWith('/orders')) return route.fulfill({ json: { orders: [order] } })
        if (url.includes('/game/balance'))
          return route.fulfill({
            json: { resource: { base_production_rate: 0.0003, tier_1_multiplier: 1 } },
          })
        return route.fulfill({ json: [] })
      })
      await page.goto(`/tests/e2e/fixtures/themed-confirmations.html?theme=${theme}&flow=${flow}`)
      if (flow === 'vault') await page.locator('li').first().click()
      const trigger = page.getByRole('button', { name: request, exact: true })
      await trigger.click()
      const dialog = page.getByRole('dialog', { name: title, exact: true })
      await expect(dialog).toBeVisible()
      await expect(dialog.getByRole('heading')).toHaveCSS('color', color)
      await dialog.getByRole('button', { name: 'Cancel', exact: true }).click()
      await expect(dialog).toBeHidden()
      expect(mutations).toBe(0)
      await trigger.click()
      await dialog.getByRole('button', { name: approve, exact: true }).click()
      await expect.poll(() => mutations).toBe(expected)
      expect(nativeDialogs).toEqual([])
      expect(errors).toEqual([])
    })
  }
}
