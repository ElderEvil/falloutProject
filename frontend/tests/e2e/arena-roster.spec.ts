import { test, expect } from '@playwright/test'

for (const width of [1280, 390]) {
  test(`selects dwellers locally and locks management during combat at ${width}px`, async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width, height: 900 })
    const names = ['Lucy MacLean', 'Maximus', 'Cooper Howard']
    const candidates = names.map((name, i) => ({
      id: `dweller-${i}`,
      name,
      level: i + 3,
      health: 80 - i * 30,
      max_health: 100,
      room_id: i === 2 ? 'arena-1' : null,
      room_name: i === 2 ? 'Arena' : null,
    }))
    let fighterA: string | null = null
    let fighterB: string | null = null
    let fighting = false
    let finished = false
    const mutations: string[] = []
    await page.route('**/static/**', (route) =>
      route.fulfill({
        contentType: 'image/svg+xml',
        body: '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="200"><rect width="100" height="200" fill="#2f6f4f"/></svg>',
      })
    )
    await page.route('**/api/v1/**', async (route) => {
      const request = route.request()
      if (request.method() === 'POST') mutations.push(request.url())
      if (request.url().endsWith('/start')) {
        const body = request.postDataJSON()
        fighterA = body.fighter_a_id
        fighterB = body.fighter_b_id
        fighting = true
        return route.fulfill({ json: { started: true } })
      }
      if (request.url().endsWith('/state')) {
        const fighter = (id: string | null) =>
          candidates
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
                next_attack_team: 'A',
                available_modes: ['duel', 'brawl', 'hunt'],
                fighter_a_id: fighterA,
                fighter_b_id: fighterB,
                fighters: [...fighter(fighterA), ...fighter(fighterB)],
                team_a: fighter(fighterA),
                team_b: fighter(fighterB),
                roster: candidates.filter((entry) => entry.room_id === 'arena-1' || fighting),
                candidates,
                fight_ready: !!fighterA && !!fighterB,
                can_start: !!fighterA && !!fighterB && !fighting,
                fight_started: fighting,
                match_done: finished,
                countdown_remaining: fighting && !finished ? 5 : 0,
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
    await expect(dialog.locator('.arena-room-detail [aria-label="Arena preview"]')).toBeVisible()
    const modes = dialog.getByRole('navigation', { name: 'Match mode' })
    await expect(modes).toBeVisible()
    await page.screenshot({ path: testInfo.outputPath('empty-arena.png'), fullPage: true })
    const bench = dialog.locator('details[aria-label="Arena bench"]')
    await bench.locator('summary').click()
    await expect(bench.getByRole('progressbar', { name: 'Cooper Howard health' })).toHaveAttribute(
      'aria-valuenow',
      '20'
    )
    await bench.screenshot({ path: testInfo.outputPath('arena-bench.png') })
    for (const [side, name] of [
      ['A', names[0]],
      ['B', names[1]],
    ]) {
      await dialog
        .getByRole('button', { name: `Select fighter 1 for Team ${side}`, exact: true })
        .click()
      const picker = dialog.getByRole('region', { name: 'Choose fighter' })
      await expect(picker.getByRole('searchbox')).toBeFocused()
      await picker.getByRole('searchbox').fill(name)
      await picker.getByRole('button', { name: new RegExp(name) }).click()
    }
    expect(mutations).toHaveLength(0)
    await expect(dialog.getByRole('button', { name: 'START FIGHT', exact: true })).toBeEnabled()
    await expect(bench.getByText('Lucy MacLean', { exact: true })).toHaveCount(0)
    await expect(bench.getByText('Cooper Howard', { exact: true })).toHaveCount(1)
    await page.screenshot({ path: testInfo.outputPath('ready-arena.png'), fullPage: true })
    expect(await dialog.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(
      true
    )
    await dialog.getByRole('button', { name: 'START FIGHT', exact: true }).click()
    await expect(dialog.getByRole('region', { name: 'Arena ring' })).toBeVisible()
    await expect(modes).toBeHidden()
    expect(mutations).toHaveLength(1)
    expect(mutations[0]).toMatch(/\/start$/)
    const management = dialog.locator('.room-management')
    for (const button of await management.getByRole('button').all()) {
      await expect(button).toBeDisabled()
    }
    finished = true
    await expect(management.getByRole('button', { name: 'Unassign All Dwellers' })).toBeEnabled()
    await expect(management.getByRole('button', { name: 'Destroy Room' })).toBeEnabled()
  })
}
