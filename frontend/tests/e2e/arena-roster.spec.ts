import { test, expect } from '@playwright/test'

for (const width of [1280, 390]) {
  test(`assigns dwellers before selecting fighters at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 })
    const roster: Array<{
      id: string
      name: string
      level: number
      health: number
      max_health: number
    }> = []
    let fighterA: string | null = null
    let fighterB: string | null = null
    const names = ['Lucy MacLean', 'Maximus', 'Cooper Howard']
    await page.route('**/api/v1/**', async (route) => {
      const request = route.request()
      const move = request.url().match(/dwellers\/dweller-(\d)\/move_to\/arena-1/)
      if (move) {
        const i = Number(move[1])
        const dweller = {
          id: `dweller-${i}`,
          name: names[i],
          level: i + 3,
          health: 80 - i * 30,
          max_health: 100,
        }
        roster.push(dweller)
        return route.fulfill({ json: { ...dweller, room_id: 'arena-1', status: 'idle' } })
      }
      if (request.url().endsWith('/fighters')) {
        const body = request.postDataJSON()
        fighterA = body.fighter_a_id
        fighterB = body.fighter_b_id
        return route.fulfill({ json: {} })
      }
      if (request.url().endsWith('/state')) {
        const fighter = (id: string | null) =>
          roster
            .filter((entry) => entry.id === id)
            .map((entry) => ({ ...entry, power: 10, is_creature: false, is_robot: false }))
        return route.fulfill({
          json: {
            rooms: [
              {
                room_id: 'arena-1',
                room_name: 'Arena',
                tier: 3,
                mode: 'duel',
                available_modes: ['duel', 'brawl', 'hunt'],
                fighter_a_id: fighterA,
                fighter_b_id: fighterB,
                fighters: [...fighter(fighterA), ...fighter(fighterB)],
                team_a: fighter(fighterA),
                team_b: fighter(fighterB),
                roster,
                fight_ready: !!fighterA && !!fighterB,
                can_start: !!fighterA && !!fighterB,
                fight_started: false,
                match_done: false,
                countdown_remaining: 0,
                winner_name: null,
                events: [],
              },
            ],
          },
        })
      }
      if (request.url().endsWith('/creatures')) return route.fulfill({ json: [] })
      return route.fulfill({ json: {} })
    })
    await page.goto('/tests/e2e/fixtures/arena-room.html')
    const dialog = page.getByRole('dialog')
    await expect(dialog.getByText('Build your arena roster', { exact: true })).toBeVisible()
    await expect(
      dialog.getByRole('button', { name: 'Choose from roster', exact: true })
    ).toHaveCount(0)
    await page.screenshot({ path: testInfo.outputPath('empty-arena.png'), fullPage: true })

    for (const name of names) {
      await dialog.getByRole('button', { name: 'Assign dwellers', exact: true }).click()
      await expect(dialog.getByText('Assign to Arena', { exact: true })).toBeVisible()
      await dialog
        .locator('.dweller-picker')
        .getByRole('button', { name: new RegExp(name) })
        .click()
      await expect.poll(() => roster.length).toBe(names.indexOf(name) + 1)
    }
    const bench = dialog.getByRole('region', { name: 'Arena bench' })
    await expect(bench.getByText('Lucy MacLean', { exact: true })).toBeVisible()
    await expect(bench.getByRole('progressbar', { name: 'Cooper Howard health' })).toHaveAttribute(
      'aria-valuenow',
      '20'
    )
    await bench.screenshot({ path: testInfo.outputPath('arena-bench.png') })
    await dialog.getByRole('button', { name: 'Choose from roster', exact: true }).first().click()
    await dialog
      .locator('.picker')
      .getByRole('button', { name: /Lucy MacLean/ })
      .click()
    await dialog.getByRole('button', { name: 'Choose from roster', exact: true }).click()
    await dialog
      .locator('.picker')
      .getByRole('button', { name: /Maximus/ })
      .click()
    await expect(dialog.getByRole('button', { name: 'START FIGHT', exact: true })).toBeEnabled()
    await expect(bench.getByText('Lucy MacLean', { exact: true })).toHaveCount(0)
    await expect(bench.getByText('Cooper Howard', { exact: true })).toHaveCount(1)
    await page.screenshot({ path: testInfo.outputPath('ready-arena.png'), fullPage: true })
    expect(await dialog.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(
      true
    )
  })
}
