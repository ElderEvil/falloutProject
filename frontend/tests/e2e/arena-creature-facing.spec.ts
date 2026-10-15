import { test, expect } from '@playwright/test'

test('creature damage feedback respects reduced motion', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.route('**/static/creature_images/**', (route) => route.abort())
  await page.goto('/tests/e2e/fixtures/arena-creature.html?damage')
  const damage = page.getByText('-15', { exact: true })
  await expect(damage).toHaveCSS('animation-name', 'none')
  await expect(damage.locator('..')).toHaveAttribute('aria-hidden', 'true')
  await page.emulateMedia({ reducedMotion: 'no-preference' })
  await expect(damage).toHaveCSS('animation-name', /damage-float/)
})

for (const { mirror, robot, enemy } of [
  { mirror: false, robot: false, enemy: false },
  { mirror: true, robot: false, enemy: false },
  { mirror: false, robot: true, enemy: true },
  { mirror: false, robot: true, enemy: false },
  { mirror: false, robot: false, enemy: true },
]) {
  test(`creature slot and picker artwork mirror=${mirror}, robot=${robot}, enemy=${enemy}`, async ({
    page,
  }) => {
    // Keep the component's image-error fallback inactive without needing a backend.
    await page.route('**/static/creature_images/**', (route) =>
      route.fulfill({
        contentType: 'image/png',
        body: Buffer.from(
          'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=',
          'base64'
        ),
      })
    )
    await page.goto(
      `/tests/e2e/fixtures/arena-creature.html?mirror=${mirror}&robot=${robot}&enemy=${enemy}`
    )
    const images = page.locator('img')
    await expect(images).toHaveCount(2)
    for (const image of await images.all()) {
      await expect(image).toHaveCSS(
        'transform',
        mirror || (robot && enemy) ? 'matrix(-1, 0, 0, 1, 0, 0)' : 'none'
      )
      await expect(image).toHaveAttribute(
        'src',
        robot ? /assembled\/eyebot\.webp/ : /assembled\/radscorpion\.webp/
      )
    }
    await expect(
      page.getByAltText(robot ? 'Training Eyebot' : 'Radscorpion', { exact: true })
    ).toHaveCount(1)
    await expect(page.getByText('20/35', { exact: true })).toBeVisible()
  })
}

for (const width of [1280, 390]) {
  test(`selects mixed Hunt and Brawl teams at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 })
    const robots = [
      { key: 'training-eyebot', name: 'Training Eyebot', power: 30, max_hp: 20, is_robot: true },
      {
        key: 'training-mr-handy',
        name: 'Training Mr. Handy',
        power: 20,
        max_hp: 30,
        is_robot: true,
      },
      {
        key: 'training-protectron',
        name: 'Training Protectron',
        power: 10,
        max_hp: 60,
        is_robot: true,
      },
    ]
    const creature = { key: 'deathclaw', name: 'Deathclaw', power: 50, max_hp: 50, is_robot: false }
    const humans = ['Alpha', 'Bravo'].map((name, i) => ({
      id: `dweller-${i}`,
      name,
      level: 1,
      health: 100,
      max_health: 100,
      power: 6,
      is_creature: false,
      is_robot: false,
    }))
    const asBot = (key: string, side: string) => {
      const entry = robots.find((robot) => robot.key === key)!
      return {
        ...entry,
        id: `${key}#${side}0`,
        level: 0,
        health: entry.max_hp,
        max_health: entry.max_hp,
        is_creature: true,
      }
    }
    let mode = 'hunt'
    let teamA = [humans[0]]
    let teamB: object[] = [
      { ...creature, id: 'deathclaw#0', level: 0, health: 50, max_health: 50, is_creature: true },
    ]
    const posts: Record<string, unknown>[] = []
    await page.route('**/api/v1/arena/**', async (route) => {
      const request = route.request()
      if (request.url().endsWith('/creatures'))
        return route.fulfill({ json: [...robots, creature] })
      if (request.method() === 'POST') {
        const body = request.postDataJSON()
        posts.push(body)
        mode = body.mode
        teamA = [humans.find((human) => human.id === body.fighter_a_id)!]
        if (body.team_a_bot_key) teamA.push(asBot(body.team_a_bot_key, 'A'))
        teamB = mode === 'brawl' ? [humans.find((human) => human.id === body.fighter_b_id)!] : teamB
        if (body.team_b_bot_key) teamB.push(asBot(body.team_b_bot_key, 'B'))
        return route.fulfill({ json: {} })
      }
      return route.fulfill({
        json: {
          rooms: [
            {
              room_id: 'arena-1',
              room_name: 'Arena',
              tier: 3,
              mode,
              available_modes: ['duel', 'brawl', 'hunt'],
              fighter_a_id: humans[0].id,
              fighter_b_id: mode === 'brawl' ? humans[1].id : null,
              fighters: [teamA[0], teamB[0]],
              team_a: teamA,
              team_b: teamB,
              roster: humans,
              fight_ready: true,
              match_done: false,
              fight_started: false,
              countdown_remaining: 0,
              can_start: true,
              winner_name: null,
              events: [],
            },
          ],
        },
      })
    })
    await page.route('**/static/**', (route) =>
      route.fulfill({
        contentType: 'image/svg+xml',
        body: '<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80"><rect width="80" height="80" fill="green"/></svg>',
      })
    )
    await page.goto('/tests/e2e/fixtures/arena-teams.html')
    const a = page.getByRole('group', { name: 'Team A partner' })
    await a.getByRole('button', { name: 'Bot', exact: true }).click()
    // Let the real one-second poll run before choosing: it must preserve the picker.
    await page.waitForTimeout(1200)
    await page.getByRole('button', { name: /Training Eyebot.*POW/ }).click()
    await expect.poll(() => posts.at(-1)?.team_a_bot_key).toBe('training-eyebot')
    await expect(page.getByAltText('Training Eyebot', { exact: true })).toHaveCSS(
      'transform',
      'none'
    )
    await page.getByRole('tab', { name: 'Hunt', exact: true }).press('ArrowLeft')
    await page.getByRole('tab', { name: 'Brawl', exact: true }).press('Enter')
    await page
      .getByRole('button', { name: /Choose from roster/ })
      .first()
      .click()
    await page.getByRole('button', { name: /^Bravo/ }).click()
    await page
      .getByRole('group', { name: 'Team B partner' })
      .getByRole('button', { name: 'Bot', exact: true })
      .click()
    await page.getByRole('button', { name: /Training Protectron.*POW/ }).click()
    await expect.poll(() => posts.at(-1)?.team_b_bot_key).toBe('training-protectron')
    await expect(page.getByAltText('Training Protectron', { exact: true })).toHaveCSS(
      'transform',
      'matrix(-1, 0, 0, 1, 0, 0)'
    )
    await expect(page.getByRole('button', { name: /START FIGHT/ })).toBeEnabled()
    await page.screenshot({ path: testInfo.outputPath('mixed-teams.png'), fullPage: true })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })
}
