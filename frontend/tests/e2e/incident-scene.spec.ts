import { test, expect } from '@playwright/test'

// The preview contract needs no backend image server.
test.beforeEach(async ({ page }) => {
  await page.route('**/static/**', (route) =>
    route.fulfill({
      contentType: 'image/svg+xml',
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect width="100" height="100" fill="green"/></svg>',
    })
  )
})

for (const [width, count] of [
  [390, 6],
  [900, 6],
  [390, 12],
  [900, 12],
]) {
  test(`${count} room residents and helpers fit the preview at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.goto(`/tests/e2e/fixtures/incident-scene.html?responders=${count}`)
    const scene = page.getByRole('region', { name: 'Incident live status' })
    await expect(scene).toContainText(`RESPONDERS · ${count}`)
    await expect(scene.locator('.dweller-name-badge')).toHaveCount(count)
    await expect(scene.locator('.dweller-health')).toHaveCount(count)
    await expect(scene.getByAltText('Deathclaw', { exact: true })).toBeVisible()
    await expect(scene.locator('.floating-effect').first().locator('..')).toHaveCSS(
      'overflow-y',
      'visible'
    )
    const bounds = (await scene.boundingBox())!
    const actors = scene.locator('.incident-responder')
    const first = (await actors.first().boundingBox())!
    for (const actor of await actors.all()) {
      const box = (await actor.boundingBox())!
      expect(Math.abs(box.y + box.height - first.y - first.height)).toBeLessThan(1)
      expect(box.y).toBeGreaterThan(bounds.y + 25)
      expect(box.y + box.height).toBeLessThan(bounds.y + bounds.height - 45)
    }
    await actors.last().scrollIntoViewIfNeeded()
    await expect(actors.last()).toBeInViewport()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  })
}

test('room art falls back and fire respects reduced motion', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/tests/e2e/fixtures/incident-scene.html?type=fire&fallback')
  const scene = page.getByRole('region', { name: 'Incident live status' })
  await expect(scene).toContainText('ROOM HAZARD')
  await expect(scene.locator('.scene-backdrop')).toHaveAttribute('src', /FOS Diner/)
  await expect(scene.locator('.flame-outer').first()).toHaveCSS('animation-name', 'none')
  await expect(scene.getByRole('progressbar', { name: 'Contained' })).toHaveAttribute(
    'aria-valuenow',
    '35'
  )
})

for (const width of [390, 900]) {
  test(`incident creature size is independent of intrinsic artwork at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.route('**/static/creature_images/**', (route) =>
      route.fulfill({
        contentType: 'image/svg+xml',
        body: '<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024"><rect width="1024" height="1024" fill="green"/></svg>',
      })
    )
    await page.goto('/tests/e2e/fixtures/incident-scene.html?responders=6')
    const scene = page.getByRole('region', { name: 'Incident live status' })
    const creature = scene.getByAltText('Deathclaw', { exact: true })
    await expect.poll(() => creature.evaluate((el: HTMLImageElement) => el.naturalWidth)).toBe(1024)
    const bounds = (await creature.boundingBox())!
    const frame = (await scene.boundingBox())!
    expect(bounds.height).toBeLessThan(frame.height * 0.7)
    expect(bounds.height).toBeGreaterThan(100)
    expect(bounds.y).toBeGreaterThan(frame.y + 32)
    expect(bounds.y + bounds.height).toBeLessThan(frame.y + frame.height - 30)
  })
}

for (const width of [390, 900]) {
  test(`fire renders as a floor hazard cluster at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/tests/e2e/fixtures/incident-scene.html?type=fire&responders=4')
    const scene = page.getByRole('region', { name: 'Incident live status' })
    const fire = scene.locator('.hazard-fire')
    await expect(fire).toHaveCount(1)
    await expect(scene.locator('.hazard-flame')).toHaveCount(3)
    await expect(fire.locator('.combatant-motion')).toHaveCount(0)

    const dweller = scene.locator('.incident-responder img').first()
    const middleFlame = scene.locator('.hazard-flame').nth(1)
    await expect
      .poll(() => dweller.evaluate((image: HTMLImageElement) => image.naturalWidth))
      .toBeGreaterThan(0)
    const dwellerBox = (await dweller.boundingBox())!
    const flameBox = (await middleFlame.boundingBox())!
    expect(flameBox.height).toBeGreaterThan(dwellerBox.height * 0.5)
    expect(flameBox.height).toBeLessThan(dwellerBox.height * 1.2)
    expect(flameBox.y + flameBox.height).toBeGreaterThan(dwellerBox.y + dwellerBox.height * 0.8)
  })
}

for (const width of [390, 900]) {
  for (const [type, label] of [
    ['raider_attack', 'Raider'],
    ['feral_ghoul_attack', 'Feral Ghoul'],
  ] as const) {
    test(`${label} keeps dweller height at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 })
      await page.goto(`/tests/e2e/fixtures/incident-scene.html?type=${type}&responders=4`)
      const scene = page.getByRole('region', { name: 'Incident live status' })
      const threat = scene.getByAltText(label, { exact: true })
      const dweller = scene.locator('.incident-responder img').first()
      for (const image of [threat, dweller]) {
        await expect
          .poll(() => image.evaluate((element: HTMLImageElement) => element.naturalWidth))
          .toBeGreaterThan(0)
      }
      const threatBox = (await threat.boundingBox())!
      const dwellerBox = (await dweller.boundingBox())!
      const ratio = threatBox.height / dwellerBox.height
      expect(ratio).toBeGreaterThan(0.85)
      expect(ratio).toBeLessThan(1.15)
    })
  }
}

test('remaining threat count sits above the threat actor', async ({ page }) => {
  await page.goto('/tests/e2e/fixtures/incident-scene.html?type=raider_attack&responders=2')
  const scene = page.getByRole('region', { name: 'Incident live status' })
  const count = scene.locator('.threat-remaining')
  const threat = scene.getByAltText('Raider', { exact: true })
  await expect(count).toHaveText('6 remaining')
  await expect(threat).toBeVisible()

  const countBox = (await count.boundingBox())!
  const threatBox = (await threat.boundingBox())!
  expect(countBox.y + countBox.height).toBeLessThanOrEqual(threatBox.y + 1)
})

for (const width of [390, 900]) {
  test(`four responders fit the roster lane at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/tests/e2e/fixtures/incident-scene.html?type=raider_attack&responders=4')
    const scene = page.getByRole('region', { name: 'Incident live status' })
    const responders = scene.locator('.incident-responder')
    await expect(responders).toHaveCount(4)
    const row = responders.first().locator('..')
    const metrics = await row.evaluate((element) => ({
      clientWidth: element.clientWidth,
      scrollWidth: element.scrollWidth,
    }))
    expect(metrics.scrollWidth).toBeLessThanOrEqual(metrics.clientWidth + 1)
    await expect(responders.last()).toBeInViewport()
  })
}

for (const width of [390, 900]) {
  test(`responders keep pets and stronger motion at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/tests/e2e/fixtures/incident-scene.html?type=raider_attack&responders=4')
    const scene = page.getByRole('region', { name: 'Incident live status' })
    const pet = scene.getByAltText('Dogmeat, Preston’s pet', { exact: true })
    await expect(pet).toBeVisible()
    await expect(scene.locator('.combat-pet .actor-ground-shadow')).toHaveCount(1)
    const motion = scene.locator('.incident-responder .combat-body').first()
    expect(
      await motion.evaluate((el) => getComputedStyle(el).getPropertyValue('--lean').trim())
    ).toBe('7deg')
    expect(
      await motion.evaluate((el) => getComputedStyle(el).getPropertyValue('--recoil').trim())
    ).toBe('8px')
  })
}
