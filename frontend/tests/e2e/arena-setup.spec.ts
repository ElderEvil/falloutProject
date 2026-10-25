import { expect, test } from '@playwright/test'

const opponents = [
  { key: 'training-eyebot', name: 'Eyebot', power: 30, max_hp: 20, is_robot: true },
  { key: 'training-protectron', name: 'Protectron', power: 10, max_hp: 60, is_robot: true },
  { key: 'radroach-swarm', name: 'Radroach swarm', power: 20, max_hp: 40, is_robot: false },
  { key: 'bloatfly', name: 'Bloatfly', power: 10, max_hp: 30, is_robot: false },
]
const people = ['Lucy', 'Maximus', 'Cooper', 'Norm'].map((name, index) => ({
  id: `dweller-${index}`,
  name,
  level: 5,
  health: 80,
  max_health: 100,
  power: 10,
  is_creature: false,
  is_robot: false,
  room_id: index ? 'generator' : 'arena-1',
  room_name: index ? 'Power Generator' : 'Arena',
  age_group: 'adult',
  race: 'human',
  active_skill: {
    name: 'Haymaker',
    icon: 'unarmed',
    description: 'Extra attack',
    charge: 0,
    queued: false,
  },
}))

for (const width of [390, 1280]) {
  for (const [mode, label] of [
    ['duel', 'Duel'],
    ['brawl', 'Team fight'],
    ['training', 'Bot training'],
    ['hunt', 'Creature hunt'],
  ]) {
    test(`${label} uses one accessible setup at ${width}px`, async ({ page }, testInfo) => {
      await page.setViewportSize({ width, height: 1000 })
      let selection: Record<string, unknown> | null = null
      const posts: Array<{ url: string; body: Record<string, unknown> }> = []
      await page.route('**/api/v1/arena/**', async (route) => {
        const request = route.request()
        if (request.url().endsWith('/creatures')) return route.fulfill({ json: opponents })
        if (request.method() === 'POST') {
          selection = request.postDataJSON()
          posts.push({ url: request.url(), body: selection! })
          return route.fulfill({ json: { started: true } })
        }
        const members = (keys: string[]) =>
          keys.map((key) => people.find((person) => person.id === selection?.[key])).filter(Boolean)
        const teamA = selection ? members(['fighter_a_id', 'fighter_c_id']) : []
        const teamB = selection
          ? ['hunt', 'training'].includes(selection.mode as string)
            ? (selection.opponent_keys as string[]).map((key, index) => {
                const opponent = opponents.find((entry) => entry.key === key)!
                return {
                  ...opponent,
                  id: `${key}#${index}`,
                  level: 1,
                  health: opponent.max_hp,
                  max_health: opponent.max_hp,
                  is_creature: !opponent.is_robot,
                }
              })
            : members(['fighter_b_id', 'fighter_d_id'])
          : []
        return route.fulfill({
          json: {
            rooms: [
              {
                room_id: 'arena-1',
                room_name: 'Arena',
                tier: 3,
                mode: selection?.mode ?? 'duel',
                available_modes: ['duel', 'brawl', 'training', 'hunt'],
                fighter_a_id: selection?.fighter_a_id ?? null,
                fighter_b_id: selection?.fighter_b_id ?? null,
                team_a: teamA,
                team_b: teamB,
                fighters: [...teamA, ...teamB],
                roster: [people[0]],
                candidates: people,
                fight_ready: false,
                match_done: false,
                fight_started: !!selection,
                countdown_remaining: selection ? 3 : 0,
                can_start: false,
                winner_name: null,
                next_attack_team: 'A',
                events: [],
              },
            ],
          },
        })
      })
      await page.goto('/tests/e2e/fixtures/arena-teams.html', { waitUntil: 'domcontentloaded' })
      const modes = page.getByRole('navigation', { name: 'Match mode' })
      await expect(modes.getByRole('button')).toHaveCount(4)
      await modes.getByRole('button', { name: new RegExp(`^${label}`) }).click()
      const preview = page.getByRole('region', { name: 'Arena preview' })
      const slotA = preview.getByRole('button', {
        name: 'Select fighter 1 for Team A',
        exact: true,
      })
      const silhouette = slotA.locator('.arena-dweller-silhouette')
      const idleColor = await silhouette.evaluate((node) => getComputedStyle(node).backgroundColor)
      await slotA.hover()
      await expect
        .poll(() => silhouette.evaluate((node) => getComputedStyle(node).backgroundColor))
        .not.toBe(idleColor)
      await page.mouse.move(0, 0)
      await slotA.focus()
      await expect
        .poll(() => silhouette.evaluate((node) => getComputedStyle(node).backgroundColor))
        .not.toBe(idleColor)
      await expect(preview.locator('.arena-empty-slot')).toHaveCount(mode === 'duel' ? 2 : 4)
      if (mode === 'duel' || mode === 'brawl') {
        const enemySilhouettes = preview
          .getByRole('button', { name: /^Select fighter .* for Team B$/ })
          .locator('.arena-dweller-silhouette')
        for (const silhouette of await enemySilhouettes.all())
          await expect(silhouette).toHaveCSS('scale', '-1 1')
      }

      const chooseDweller = async (side: 'A' | 'B', index: number, name: string) => {
        await preview
          .getByRole('button', { name: `Select fighter ${index} for Team ${side}`, exact: true })
          .click()
        const picker = page.getByRole('region', { name: 'Choose fighter' })
        await expect(picker.getByRole('searchbox')).toBeFocused()
        if (name !== 'Lucy') await expect(picker).toContainText('Power Generator → Arena')
        await picker.getByRole('searchbox').fill(name)
        await picker.getByRole('button', { name: new RegExp(name) }).click()
      }
      await chooseDweller('A', 1, 'Lucy')
      const controls = preview.getByRole('group', { name: 'Controls for Lucy' })
      const portraitBounds = (await slotA.boundingBox())!
      const controlsBounds = (await controls.boundingBox())!
      expect(controlsBounds.y).toBeGreaterThanOrEqual(portraitBounds.y + portraitBounds.height)
      await controls.getByRole('button', { name: 'Remove Lucy from fight' }).click()
      await expect(slotA).toContainText('Add dweller')
      await expect(slotA).toBeFocused()
      expect(posts).toHaveLength(0)
      await chooseDweller('A', 1, 'Lucy')
      if (mode !== 'duel') await chooseDweller('A', 2, 'Maximus')
      if (mode === 'duel') await chooseDweller('B', 1, 'Maximus')
      else if (mode === 'brawl') {
        await chooseDweller('B', 1, 'Cooper')
        await chooseDweller('B', 2, 'Norm')
      } else {
        const kind = mode === 'training' ? 'bot' : 'creature'
        await expect(
          preview.getByRole('button', { name: new RegExp(`^Select ${kind}`) })
        ).toHaveCount(2)
        const names =
          mode === 'training' ? ['Eyebot', 'Protectron'] : ['Radroach swarm', 'Bloatfly']
        for (const [index, name] of names.entries()) {
          await preview
            .getByRole('button', { name: `Select ${kind} ${index + 1} for Team B`, exact: true })
            .click()
          const picker = page.getByRole('region', { name: `Choose ${kind}` })
          if (kind === 'bot') await expect(picker).not.toContainText('Radroach')
          else await expect(picker).not.toContainText('Eyebot')
          await picker.getByRole('button', { name: new RegExp(name) }).click()
        }
      }
      expect(posts).toHaveLength(0)
      await expect(preview.locator('button [data-skill-icon]')).toHaveCount(
        mode === 'brawl' ? 4 : 2
      )
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
        true
      )
      await page.screenshot({
        path: testInfo.outputPath(`arena-${mode}-${width}.png`),
        fullPage: true,
      })
      await page.getByRole('button', { name: 'START FIGHT', exact: true }).click()
      await expect(page.getByRole('region', { name: 'Arena ring' })).toBeVisible()
      await expect(modes).toBeHidden()
      expect(posts).toHaveLength(1)
      expect(posts[0].url).toMatch(/\/start$/)
      expect(posts[0].body.mode).toBe(mode)
      expect(posts[0].body.fighter_a_id).toBe('dweller-0')
    })
  }
}
