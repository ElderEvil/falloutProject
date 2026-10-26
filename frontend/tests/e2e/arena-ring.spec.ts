import { test, expect } from '@playwright/test'
import { fileURLToPath } from 'node:url'

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
