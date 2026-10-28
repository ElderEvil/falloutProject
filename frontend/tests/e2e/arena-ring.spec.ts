import { test, expect } from '@playwright/test'
import { fileURLToPath } from 'node:url'

test.beforeEach(async ({ page }) => {
  await page.route('**/static/**', (route) =>
    route.fulfill({
      contentType: 'image/svg+xml',
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect width="100" height="100" fill="green"/></svg>',
    })
  )
})

for (const width of [390, 1280]) {
  test(`skill impact artwork remains visible with reduced motion at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.emulateMedia({ reducedMotion: 'reduce' })
    const image = page.waitForResponse((response) =>
      response.url().includes('/assets/combat/skill-hit.webp')
    )
    await page.goto('/tests/e2e/fixtures/arena-ring.html?mode=duel&pet-attack=1&skill-hit=1')
    expect((await image).ok()).toBe(true)
    const impact = page.locator('.skill-hit')
    await expect(impact).toHaveCount(1)
    await expect(impact).toBeVisible()
    await expect(impact).toHaveCSS('animation-name', 'none')
    await expect(impact).toHaveCSS('background-position', '26.6667% 0px')
  })
}

for (const actor of ['Alpha', 'Bravo']) {
  test(`${actor}'s attack effect is anchored toward the opposing fighter`, async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.goto(`/tests/e2e/fixtures/arena-ring.html?mode=duel&pet-attack=1&actor=${actor}`)
    const fighters = page.locator('.ring-fighter')
    const attacker = fighters.filter({
      has: page.locator(`.fighter-meters span[title="${actor}"]`),
    })
    const motion = attacker.locator('.combatant-motion').first()
    const effect = motion.locator('.combat-effect')
    const [bodyBox, effectBox] = await Promise.all([motion.boundingBox(), effect.boundingBox()])
    expect(bodyBox).not.toBeNull()
    expect(effectBox).not.toBeNull()
    const displacement = effectBox!.x + effectBox!.width / 2 - bodyBox!.x - bodyBox!.width / 2
    expect(actor === 'Alpha' ? displacement : -displacement).toBeGreaterThan(bodyBox!.width * 0.4)
  })
}

test('damaged fighters show a red cue without highlighting the attacker or pets', async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/tests/e2e/fixtures/arena-ring.html?mode=duel&pets=1&pet-attack=1')
  const fighters = page.locator('.ring-fighter')
  const attacker = fighters.filter({ has: page.locator('.fighter-meters span[title="Alpha"]') })
  const target = fighters.filter({ has: page.locator('.fighter-meters span[title="Bravo"]') })
  const targetBody = target.locator('.fighter-portrait > .combatant-motion > .combat-body')
  const attackerBody = attacker.locator('.fighter-portrait > .combatant-motion > .combat-body')
  await expect(targetBody).toHaveCSS('filter', /drop-shadow.*rgb\(255, 0, 0\)/)
  await expect(attackerBody).toHaveCSS('filter', 'none')
  await expect(target.locator('.combat-pet .combat-body')).toHaveCSS('filter', 'none')
})

test('fighters and pets have soft ground shadows that stay on the floor during attacks', async ({
  page,
}) => {
  await page.goto('/tests/e2e/fixtures/arena-ring.html?mode=duel&pets=1&pet-attack=1')
  const actors = page.locator('.combatant-motion')
  await expect(actors).toHaveCount(4)
  for (const actor of await actors.all()) {
    const shadow = await actor.evaluate((element) => {
      const style = getComputedStyle(element, '::before')
      return {
        content: style.content,
        width: parseFloat(style.width),
        height: parseFloat(style.height),
        bottom: style.bottom,
        filter: style.filter,
        pointerEvents: style.pointerEvents,
        transform: style.transform,
      }
    })
    expect(shadow.content).toBe('""')
    expect(shadow.width).toBeGreaterThan(shadow.height * 3)
    expect(shadow.height).toBeGreaterThan(0)
    expect(shadow.bottom).toBe('0px')
    expect(shadow.filter).toContain('blur')
    expect(shadow.pointerEvents).toBe('none')
  }
})

for (const actor of ['Alpha', 'Bravo']) {
  test(`${actor}'s pet lunges inward without damage effects`, async ({ page }) => {
    await page.goto(
      `/tests/e2e/fixtures/arena-ring.html?mode=duel&pets=1&pet-attack=1&actor=${actor}`
    )
    const fighter = page
      .locator('.ring-fighter')
      .filter({ has: page.locator(`.fighter-meters span[title="${actor}"]`) })
    const body = fighter.locator('.combat-pet .combat-body')
    await expect(body).toHaveClass(/combat-body--attack/)
    const movement = await body.evaluate((element) => {
      for (const animation of element.getAnimations()) {
        animation.pause()
        animation.currentTime = 50
      }
      return new DOMMatrixReadOnly(getComputedStyle(element).transform).m41
    })
    expect(actor === 'Alpha' ? movement : -movement).toBeGreaterThan(0)
    await expect(page.locator('.combat-pet .combat-body--hit')).toHaveCount(0)
    await expect(page.locator('.combat-pet .combat-effect')).toHaveCount(0)
  })
}

test('a pet stays unharmed when its owner is knocked out', async ({ page }) => {
  await page.goto('/tests/e2e/fixtures/arena-ring.html?mode=duel&pets=1&knocked-out=Alpha')
  const pet = page.locator('.ring-fighter').first().locator('.combat-pet')
  await expect(pet).toBeVisible()
  const opacity = await pet.evaluate((element) => {
    let value = 1
    for (let node: Element | null = element; node; node = node.parentElement)
      value *= Number(getComputedStyle(node).opacity)
    return value
  })
  expect(opacity).toBe(1)
  await expect(pet.locator('.combat-body--hit')).toHaveCount(0)
})

for (const width of [390, 1280]) {
  for (const mode of ['duel', 'hunt']) {
    test(`pets share their owners' ground without extra fighters in ${mode} at ${width}px`, async ({
      page,
    }) => {
      await page.setViewportSize({ width, height: 900 })
      await page.route('**/static/**', (route) =>
        route.fulfill({
          path: fileURLToPath(
            new URL(
              route.request().url().includes('pet_images')
                ? route.request().url().includes('CX404')
                  ? '../../../backend/app/static/pet_images/FOS CX404.png'
                  : '../../../backend/app/static/pet_images/FOS American Shorthair.png'
                : '../../../backend/app/static/dweller_thumbnails/base/FOS_Dw_Default_Human_Female.webp',
              import.meta.url
            )
          ),
        })
      )
      await page.goto(`/tests/e2e/fixtures/arena-ring.html?mode=${mode}&pets=1&portrait=1`)
      const ring = page.getByRole('region', { name: 'Arena ring' })
      const pets = ring.locator('.combat-pet')
      await expect(pets).toHaveCount(2)
      const bounds = (await ring.boundingBox())!
      for (const pet of await pets.all()) {
        await expect
          .poll(() => pet.locator('img').evaluate((img: HTMLImageElement) => img.naturalWidth))
          .toBeGreaterThan(0)
        const box = (await pet.boundingBox())!
        const owner = (await pet.locator('..').boundingBox())!
        expect(Math.abs(box.y + box.height - owner.y - owner.height)).toBeLessThan(1)
        expect(box.height).toBeLessThan(owner.height * 0.4)
        expect(box.x).toBeGreaterThanOrEqual(bounds.x)
        expect(box.x + box.width).toBeLessThanOrEqual(bounds.x + bounds.width)
      }
      await expect(ring.locator('.ring-fighter')).toHaveCount(mode === 'duel' ? 2 : 4)
    })
  }
}

for (const width of [390, 1280]) {
  test(`ring depth, scale and themed activation at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.route('**/static/**', (route) =>
      route.fulfill({
        contentType: 'image/svg+xml',
        body: '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect width="100" height="100" fill="green"/></svg>',
      })
    )
    await page.goto('/tests/e2e/fixtures/arena-ring.html')
    const ring = page.getByRole('region', { name: 'Arena ring' })
    const actors = ring.locator('.ring-fighter')
    const front = await actors.nth(0).boundingBox()
    const rear = await actors.nth(1).boundingBox()
    expect(rear!.y + rear!.height).toBeLessThan(front!.y + front!.height)
    const large = await ring.getByAltText('deathclaw#0', { exact: true }).boundingBox()
    const small = await ring.getByAltText('radroach-swarm#1', { exact: true }).boundingBox()
    expect(large!.width).toBeGreaterThan(small!.width * 2)
    expect(large!.height).toBeGreaterThan(small!.height * 2)
    const activate = ring.getByRole('button', {
      name: 'Use Aimed Shot from Alpha on deathclaw#0',
      exact: true,
    })
    const themeColor = await ring
      .getByText('Alpha', { exact: true })
      .evaluate((el) => getComputedStyle(el).color)
    await expect(activate).toHaveCSS('color', themeColor)
    await activate.hover()
    const tooltip = page.locator('[data-slot="tooltip-content"]')
    await expect(tooltip).toBeVisible()
    await expect(tooltip).toContainText('Alpha · Aimed Shot')
    await expect(tooltip).toHaveCSS('color', themeColor)
    await activate.click()
    await expect(activate).toHaveCount(0)
    await expect(actors.nth(0)).toContainText('QUEUED')
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })
}

test('countdown is centered in the preview and clears when combat begins', async ({ page }) => {
  await page.route('**/static/**', (route) => route.abort())
  await page.goto('/tests/e2e/fixtures/arena-ring.html?countdown=3', {
    waitUntil: 'domcontentloaded',
  })
  const ring = page.getByRole('region', { name: 'Arena ring' })
  await expect(ring.getByRole('status')).toContainText('STARTING IN')
  await expect(ring.locator('.countdown-number')).toHaveText('3')
  const scene = await ring.boundingBox()
  const counter = await ring.locator('.countdown-number').boundingBox()
  expect(Math.abs(counter!.x + counter!.width / 2 - (scene!.x + scene!.width / 2))).toBeLessThan(2)
  await expect(ring.getByRole('button', { name: /from Alpha/ })).toHaveCount(0)
  await expect(ring.locator('.countdown-number')).toHaveCount(0)
  await expect(ring.getByRole('button', { name: /from Alpha/ })).toBeEnabled()
})

for (const width of [390, 1280]) {
  test(`duel fighters center in mirrored halves at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/tests/e2e/fixtures/arena-ring.html?mode=duel')
    const ring = page.getByRole('region', { name: 'Arena ring' })
    const actors = ring.locator('.ring-fighter')
    await expect(actors).toHaveCount(2)
    const scene = (await ring.boundingBox())!
    const a = (await actors.nth(0).boundingBox())!
    const b = (await actors.nth(1).boundingBox())!
    const centerA = a.x + a.width / 2
    const centerB = b.x + b.width / 2
    expect(centerA).toBeLessThan(scene.x + scene.width / 2)
    expect(centerB).toBeGreaterThan(scene.x + scene.width / 2)
    expect(Math.abs((centerA + centerB) / 2 - (scene.x + scene.width / 2))).toBeLessThan(1)
    for (const actor of await actors.all()) {
      const box = (await actor.boundingBox())!
      const half = (await actor.locator('..').boundingBox())!
      expect(Math.abs(box.x + box.width / 2 - (half.x + half.width / 2))).toBeLessThan(1)
    }
    expect(Math.abs(a.y + a.height - (b.y + b.height))).toBeLessThan(1)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })
}

test('team B portrait faces inward while its skill control stays upright', async ({ page }) => {
  await page.route('**/static/test-dweller.png', (route) =>
    route.fulfill({
      contentType: 'image/svg+xml',
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><path d="M0 0h100L0 100z" fill="green"/></svg>',
    })
  )
  await page.goto('/tests/e2e/fixtures/arena-ring.html?mode=duel&portrait=1')
  const defender = page.getByRole('region', { name: 'Arena ring' }).locator('.ring-fighter').nth(1)
  const marker = defender.getByRole('button', { name: 'Use Aimed Shot from Alpha on Bravo' })
  const horizontalScale = (element: Element) => {
    let scale = 1
    for (let node: Element | null = element; node; node = node.parentElement) {
      const style = getComputedStyle(node)
      if (style.scale !== 'none') scale *= Number(style.scale.split(' ')[0])
      if (style.transform !== 'none') scale *= new DOMMatrix(style.transform).a
    }
    return scale
  }
  expect(await marker.evaluate(horizontalScale)).toBeGreaterThan(0)
  expect(
    await defender.getByAltText('Bravo', { exact: true }).evaluate(horizontalScale)
  ).toBeLessThan(0)
})

for (const [creature, lift] of [
  ['bloatfly', 0.2],
  ['training-eyebot', 0.06],
  ['training-mr-handy', 0.06],
  ['deathclaw', 0],
] as const) {
  test(`${creature} floats at its intended height while its shadow stays on the floor`, async ({
    page,
  }) => {
    await page.goto(`/tests/e2e/fixtures/arena-ring.html?enemy=${creature}`)
    const motion = page
      .locator('.ring-fighter')
      .filter({ has: page.getByTitle(`${creature}#0`, { exact: true }) })
      .locator('.fighter-portrait > .combatant-motion')
    const geometry = await motion.evaluate((element) => {
      const frame = element.getBoundingClientRect()
      const image = element.querySelector('img')!.getBoundingClientRect()
      return {
        lift: (frame.bottom - image.bottom) / frame.height,
        shadowBottom: getComputedStyle(element, '::before').bottom,
      }
    })
    expect(geometry.lift).toBeCloseTo(lift, 2)
    expect(geometry.shadowBottom).toBe('0px')
  })
}
