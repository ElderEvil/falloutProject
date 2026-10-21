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
      ['second', 30, 'r1'],
      ['third', 60, 'r1'],
      ['annex', 15, 'r4'],
    ].map(([id, minutes, roomId]) => ({
      id,
      dweller_id: id,
      room_id: roomId,
      stat_being_trained: roomId === 'r2' ? 'endurance' : 'strength',
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
          json: [
            ...sessions.map((session) => ({
              id: session.id,
              first_name:
                session.id === 'first' ? 'Alice' : session.id === 'soon' ? 'Bob' : 'Carol',
              last_name: 'Vault',
              room_id: session.room_id,
              status: 'training',
              level: 1,
            })),
            {
              id: 'apprentice',
              first_name: 'Ada',
              last_name: 'Learner',
              room_id: 'r3',
              status: 'idle',
              level: 1,
              apprentice_stat: 'agility',
              agility: 3,
              apprentice_started_at: new Date(Date.now() - 60 * 60_000).toISOString(),
            },
          ],
        })
      if (route.request().url().includes('/rooms/vault/'))
        return route.fulfill({
          json: [
            { id: 'r1', name: 'Weight Room', size: 6 },
            { id: 'r2', name: 'Fitness Room' },
            { id: 'r3', name: 'Diner', tier: 1 },
            { id: 'r4', name: 'Annex' },
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
    const initialGoal = page.getByRole('group', { name: 'Training goal for Alice Vault' })
    await initialGoal.getByRole('button', { name: 'Decrease goal for Alice Vault' }).click()
    await expect(initialGoal.locator('output')).toHaveText('9')
    await expect(toggle).toHaveAttribute('aria-pressed', 'false')
    await initialGoal.getByRole('button', { name: 'Increase goal for Alice Vault' }).click()
    await expect(initialGoal.locator('output')).toHaveText('10')
    await toggle.click()
    await expect(toggle).toHaveAttribute('aria-pressed', 'true')
    expect(changes).toEqual([true])
    const fits = await toggle.evaluate((element) => {
      const bounds = element.closest('.training-queue-header')!.getBoundingClientRect()
      const button = element.getBoundingClientRect()
      const title = element
        .closest('.training-queue-header')!
        .querySelector('h3')!
        .getBoundingClientRect()
      return (
        (button.left >= title.right || button.top >= title.bottom) && button.right <= bounds.right
      )
    })
    expect(fits).toBe(true)
    await page.reload()
    await expect(toggle).toHaveAttribute('aria-pressed', 'true')
    const cards = page.locator('.training-progress-card')
    await expect(cards).toHaveCount(6)
    const queueHeading = (await page
      .getByRole('heading', { name: 'Training Queue', exact: true })
      .boundingBox())!
    const queueBox = (await page.locator('.training-queue-content').boundingBox())!
    expect(queueHeading.y + queueHeading.height).toBeLessThan(queueBox.y)
    await expect(cards.nth(0)).toContainText('Alice Vault')
    await expect(cards.nth(1)).toContainText('Carol Vault')
    await expect(cards.nth(5)).toContainText('Bob Vault')
    await expect(cards.nth(0)).toContainText('Strength 5 → 6')
    const aliceGoal = page.getByRole('group', { name: 'Training goal for Alice Vault' })
    const goalValue = aliceGoal.locator('output')
    const minus = aliceGoal.getByRole('button', { name: 'Decrease goal for Alice Vault' })
    const plus = aliceGoal.getByRole('button', { name: 'Increase goal for Alice Vault' })
    await expect(goalValue).toHaveText('10')
    await expect(plus).toBeDisabled()
    for (const value of [9, 8, 7, 6]) {
      await minus.click()
      await expect(goalValue).toHaveText(String(value))
    }
    await expect(minus).toBeDisabled()
    await plus.click()
    await expect(goalValue).toHaveText('7')
    await page.reload()
    await expect(goalValue).toHaveText('7')
    await expect(
      page.getByRole('group', { name: 'Training goal for Bob Vault' }).locator('output')
    ).toHaveText('10')
    await expect(
      page.getByRole('region', { name: 'Weight Room' }).locator('.training-progress-card')
    ).toHaveCount(4)
    await expect(
      page.getByRole('region', { name: 'Fitness Room' }).locator('.training-progress-card')
    ).toHaveCount(1)
    const apprentice = page.locator('.learning-progress-card').filter({ hasText: 'Ada Learner' })
    await expect(apprentice).toContainText('Apprentice')
    await expect(apprentice).toContainText('Agility 3 → 4')
    await expect(apprentice).toContainText('Diner')
    await expect(apprentice.getByRole('button')).toHaveCount(0)
    expect(
      await apprentice.evaluate((element) => {
        const grid = element.parentElement!
        const bounds = element.getBoundingClientRect()
        const rail = grid.getBoundingClientRect()
        return Math.abs(bounds.right - rail.right) < 1 && Math.abs(bounds.left - rail.left) < 1
      })
    ).toBe(true)
    await expect(page.locator('.learning-progress-card')).toHaveCount(7)
    const first = (await cards.nth(0).boundingBox())!
    const second = (await cards.nth(1).boundingBox())!
    if (theme === 'fnv') {
      expect(second.y).toBeGreaterThan(first.y)
    } else {
      expect(second.y).toBe(first.y)
      expect(second.x).toBeGreaterThan(first.x)
      expect(first.width).toBeLessThanOrEqual(320)
      const roomCards = await page
        .getByRole('region', { name: 'Weight Room' })
        .locator('.training-progress-card')
        .evaluateAll((elements) => elements.map((element) => element.getBoundingClientRect()))
      expect(new Set(roomCards.map((bounds) => bounds.y)).size).toBe(1)
      expect(roomCards[3]!.right).toBeLessThanOrEqual(queueBox.x + queueBox.width)
    }
    const strengthGroup = page
      .locator('details')
      .filter({ has: page.locator('summary').filter({ hasText: 'Strength' }) })
    await expect(page.locator('.training-queue-content')).toHaveCSS('border-top-width', '0px')
    await expect(strengthGroup).toHaveCSS('border-top-width', '2px')
    const summary = strengthGroup.locator('summary')
    await expect(summary).toHaveText('Strength 5 training · 2 rooms')
    await expect(page.locator('details')).toHaveCount(2)
    await summary.focus()
    await page.keyboard.press('Enter')
    await expect(cards.nth(0)).not.toBeVisible()
    await expect(summary).toBeVisible()
    await expect(
      page
        .getByRole('region', { name: 'Fitness Room', exact: true })
        .locator('.training-progress-card')
    ).toBeVisible()
    const bobGoal = page.getByRole('group', { name: 'Training goal for Bob Vault' })
    await bobGoal.getByRole('button', { name: 'Decrease goal for Bob Vault' }).click()
    await expect(bobGoal.locator('output')).toHaveText('9')
    await expect(strengthGroup).not.toHaveAttribute('open')
    await summary.focus()
    await page.keyboard.press('Enter')
    await expect(cards.nth(0)).toBeVisible()
    await expect(cards.nth(0)).toContainText('Soon')
    await expect(
      cards.nth(0).getByRole('progressbar', { name: 'Strength training progress for Alice Vault' })
    ).toBeVisible()
    const name = cards.nth(0).getByText('Alice Vault', { exact: true })
    await name.focus()
    await expect(page.getByRole('tooltip')).toHaveText('Alice Vault')
    await expect(page.getByRole('tooltip')).toHaveCSS(
      'color',
      theme === 'fo4' ? 'rgb(0, 255, 0)' : theme === 'fo3' ? 'rgb(0, 255, 159)' : 'rgb(255, 183, 0)'
    )
    await page.keyboard.press('Escape')
    await expect(name).not.toHaveAttribute('title')
    const rowsFit = await page
      .locator('.learning-progress-card')
      .evaluateAll((rows) => rows.every((row) => row.scrollWidth <= row.clientWidth))
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

for (const width of [1280, 360]) {
  test(`training room stats fit without horizontal scrolling at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    const stats = [
      'strength',
      'perception',
      'endurance',
      'charisma',
      'intelligence',
      'agility',
      'luck',
    ]
    const names = [
      'Weight Room',
      'Armory',
      'Fitness Room',
      'Lounge',
      'Classroom',
      'Athletics Room',
      'Game Room',
    ]
    await page.route('**/api/v1/**', async (route) => {
      if (route.request().url().includes('/vaults/vault-1'))
        return route.fulfill({ json: { id: 'vault-1', number: 1, continuous_training: false } })
      if (route.request().url().includes('/rooms/vault/'))
        return route.fulfill({
          json: stats.map((ability, index) => ({
            id: ability,
            name: names[index],
            ability,
            tier: 1,
            category: 'training',
            size: 9,
            capacity: 6,
          })),
        })
      return route.fulfill({ json: [] })
    })
    await page.goto('/tests/e2e/fixtures/continuous-training.html?full=1')
    const region = page.getByRole('region', { name: 'Training rooms by SPECIAL stat', exact: true })
    const groups = region.locator(':scope > section')
    await expect(groups).toHaveCount(7)
    const bounds = await groups.evaluateAll((elements) =>
      elements.map((element) => ({
        top: element.getBoundingClientRect().top,
        fits: element.scrollWidth <= element.clientWidth,
      }))
    )
    expect(bounds.every((element) => element.fits)).toBe(true)
    expect(await region.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(
      true
    )
    const roomLink = page.getByRole('link', { name: 'Open Weight Room', exact: true })
    await expect(roomLink).toHaveAttribute('href', '/vault/vault-1?roomId=strength')
    await roomLink.focus()
    await expect(page.getByRole('tooltip')).toHaveText('Open Weight Room')
    await expect(roomLink).not.toHaveAttribute('title')
    await page.keyboard.press('Escape')
    const capacityGroup = page.getByRole('group', { name: 'Overall training capacity' })
    await expect(capacityGroup.getByRole('progressbar')).toHaveCount(0)
    expect(
      await capacityGroup.evaluate(
        (element) =>
          Math.abs(
            element.getBoundingClientRect().right -
              element.parentElement!.getBoundingClientRect().right
          ) < 1
      )
    ).toBe(true)
    if (width === 1280) {
      expect(new Set(bounds.map((element) => element.top)).size).toBe(1)
      const title = (await page
        .getByRole('heading', { name: 'Training Rooms', exact: true })
        .boundingBox())!
      const capacity = (await page
        .getByRole('group', { name: 'Overall training capacity' })
        .boundingBox())!
      expect(capacity.x).toBeGreaterThan(title.x + title.width)
      expect(capacity.y).toBeLessThan(title.y + title.height)
    }
    await page.screenshot({ path: test.info().outputPath(`training-rooms-${width}.png`) })
  })
}

for (const [size, capacity, desktopColumns] of [
  [3, 2, 2],
  [6, 4, 4],
  [9, 6, 3],
] as const) {
  for (const width of [1280, 360]) {
    test(`capacity ${capacity} uses its room shape at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 1000 })
      const sessions = Array.from({ length: capacity }, (_, index) => ({
        id: `training-${index}`,
        dweller_id: `dweller-${index}`,
        room_id: 'room-1',
        stat_being_trained: 'strength',
        status: 'active',
        current_stat_value: 5,
        target_stat_value: 6,
        goal_stat_value: 10,
        progress: 0,
        started_at: new Date().toISOString(),
        estimated_completion_at: new Date(Date.now() + 3600_000).toISOString(),
      }))
      await page.route('**/api/v1/**', async (route) => {
        const url = route.request().url()
        if (url.endsWith('/cancel')) {
          const cancelled = sessions.shift()!
          return route.fulfill({ json: { ...cancelled, status: 'cancelled' } })
        }
        if (url.endsWith('/vaults/vault-1'))
          return route.fulfill({ json: { id: 'vault-1', number: 1 } })
        if (url.includes('/training/vault/')) return route.fulfill({ json: sessions })
        if (url.includes('/rooms/vault/'))
          return route.fulfill({ json: [{ id: 'room-1', name: 'Weight Room', size }] })
        if (url.includes('/dwellers/'))
          return route.fulfill({
            json: sessions.map((session) => ({
              id: session.dweller_id,
              first_name: 'Training',
              last_name: session.dweller_id,
            })),
          })
        return route.fulfill({ json: [] })
      })
      await page.goto('/tests/e2e/fixtures/continuous-training.html')
      const cards = page
        .getByRole('region', { name: 'Weight Room', exact: true })
        .locator('.training-progress-card')
      await expect(cards).toHaveCount(capacity)
      const bounds = await cards.evaluateAll((elements) =>
        elements.map((element) => {
          const rect = element.getBoundingClientRect()
          return { x: rect.x, y: rect.y, width: rect.width, right: rect.right }
        })
      )
      const columns = width === 360 ? 1 : desktopColumns
      expect(new Set(bounds.map((rect) => rect.x)).size).toBe(columns)
      expect(new Set(bounds.map((rect) => rect.y)).size).toBe(Math.ceil(capacity / columns))
      const grid = (await cards.first().locator('..').boundingBox())!
      expect(Math.abs(bounds[columns - 1]!.right - grid.x - grid.width)).toBeLessThan(1)
      expect(
        await page.locator('body').evaluate((element) => element.scrollWidth <= innerWidth)
      ).toBe(true)
      await page.screenshot({
        path: test.info().outputPath(`room-${capacity}-${width}.png`),
        fullPage: true,
      })
      const cancel = cards.first().getByRole('button', { name: 'Cancel', exact: true })
      await page.mouse.move(0, 0)
      await expect(cancel).toHaveCSS('opacity', '0')
      await cards
        .first()
        .getByRole('button', { name: /Decrease goal/ })
        .focus()
      await expect(cancel).toHaveCSS('opacity', '1')
      await cancel.focus()
      await expect(cancel).toBeFocused()
      await cards.first().hover()
      await cancel.click()
      await expect(cards).toHaveCount(capacity - 1)
      expect(Math.abs((await cards.first().boundingBox())!.width - bounds[0]!.width)).toBeLessThan(
        1
      )
    })
  }
}
