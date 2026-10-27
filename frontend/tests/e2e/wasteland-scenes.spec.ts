import { expect, test } from '@playwright/test'
import { fileURLToPath } from 'node:url'

for (const width of [390, 1280]) {
  test(`equipped pet appears in the expedition combat preview at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.route('**/static/**', (route) =>
      route.fulfill({
        path: fileURLToPath(
          new URL(
            route.request().url().includes('pet_images')
              ? '../../../backend/app/static/pet_images/FOS CX404.png'
              : '../../../backend/app/static/dweller_thumbnails/base/FOS_Dw_Default_Human_Female.webp',
            import.meta.url
          )
        ),
      })
    )
    await page.goto('/tests/e2e/fixtures/wasteland-scenes.html')
    await page.getByRole('combobox', { name: 'Preview pet' }).click()
    await page.getByRole('option', { name: 'CX404', exact: true }).click()
    await page.getByRole('button', { name: 'Preview briefing', exact: true }).click()
    await expect(
      page.getByRole('dialog').getByAltText('CX404, Lucy MacLean’s pet', { exact: true })
    ).toBeVisible()
    await page.getByRole('button', { name: 'Close preview', exact: true }).click()
    await page.getByRole('button', { name: 'Preview combat layout', exact: true }).click()
    const dialog = page.getByRole('dialog')
    const pet = dialog.getByAltText('CX404, Lucy MacLean’s pet', { exact: true })
    await expect
      .poll(() => pet.evaluate((image: HTMLImageElement) => image.naturalWidth))
      .toBeGreaterThan(0)
    await expect(dialog.locator('.fighter-meters')).toHaveCount(2)
    const companion = (await pet.boundingBox())!
    const portrait = (await dialog.locator('.fighter-portrait').first().boundingBox())!
    expect(companion.height).toBeLessThan(portrait.height * 0.4)
    expect(Math.abs(companion.y + companion.height - portrait.y - portrait.height)).toBeLessThan(1)
  })
}

for (const viewport of [
  { width: 1280, height: 720 },
  { width: 390, height: 844 },
]) {
  test(`single discovered site fits the popup at ${viewport.width}px`, async ({ page }) => {
    await page.setViewportSize(viewport)
    await page.route('**/api/v1/explorations/preview-picker/site', (route) =>
      route.fulfill({ json: null })
    )
    await page.route('**/api/v1/explorations/preview-picker/site/available', (route) =>
      route.fulfill({
        json: [
          {
            id: 'collapsed_subway',
            name: 'Collapsed Subway',
            scene_id: 'subway_station',
            flavor:
              'A raider is guarding the broken platform. Sealed supplies lie behind the counter.',
            min_dweller_level: 1,
            room_total: 1,
            enemy_names: ['Raider'],
            threat: 'Low',
          },
        ],
      })
    )
    await page.goto('/tests/e2e/fixtures/wasteland-scenes.html?picker=1')
    const dialog = page.getByRole('dialog')
    await expect(dialog).toContainText('Rachel Miller discovered a site.')
    const overflow = await dialog.evaluate((element) =>
      [...element.querySelectorAll('*')]
        .filter((child) => /auto|scroll/.test(getComputedStyle(child).overflowY))
        .map((child) => child.scrollHeight - child.clientHeight)
    )
    expect(overflow.every((height) => height <= 1)).toBe(true)
    await expect(dialog.getByRole('button', { name: 'Enter', exact: true })).toBeInViewport()
  })
}

test('raiders match dweller height and both scale when the scene container resizes', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.route('**/static/**', (route) =>
    route.fulfill({
      path: fileURLToPath(
        new URL(
          route.request().url().includes('raider')
            ? '../../../backend/app/static/raider_images/variants/sable.webp'
            : '../../../backend/app/static/dweller_thumbnails/base/FOS_Dw_Default_Human_Female.webp',
          import.meta.url
        )
      ),
    })
  )
  await page.goto('/tests/e2e/fixtures/wasteland-scenes.html')
  await page.getByRole('combobox', { name: 'Preview location' }).click()
  await page.getByRole('option', { name: 'Abandoned supermarket', exact: true }).click()
  await page.getByRole('button', { name: 'Preview combat layout', exact: true }).click()
  const dialog = page.getByRole('dialog')
  const scene = dialog.getByRole('region', { name: 'Abandoned supermarket', exact: true })
  const dweller = scene.getByAltText('Lucy MacLean', { exact: true })
  const raider = scene.getByAltText('Raider', { exact: true })
  for (const actor of [dweller, raider]) {
    await expect
      .poll(() => actor.evaluate((el: HTMLImageElement) => el.naturalWidth))
      .toBeGreaterThan(0)
  }
  await page.waitForTimeout(150)
  const before = {
    scene: (await scene.boundingBox())!,
    dweller: (await dweller.boundingBox())!,
    raider: (await raider.boundingBox())!,
  }
  expect(before.raider.height / before.dweller.height).toBeGreaterThan(0.85)
  expect(before.raider.height / before.dweller.height).toBeLessThan(1.15)
  // Keep the viewport fixed: scaling must follow the picture, not a viewport breakpoint.
  await dialog.getByLabel('Battlefield space').evaluate((el) => {
    el.parentElement!.style.height = '320px'
  })
  await page.waitForTimeout(100)
  const after = {
    scene: (await scene.boundingBox())!,
    dweller: (await dweller.boundingBox())!,
    raider: (await raider.boundingBox())!,
  }
  const ratio = after.scene.height / before.scene.height
  expect(ratio).toBeLessThan(0.8)
  expect(after.dweller.height / before.dweller.height).toBeCloseTo(ratio, 1)
  expect(after.raider.height / before.raider.height).toBeCloseTo(ratio, 1)
})

for (const [width, height] of [
  [1280, 720],
  [1280, 600],
  [1920, 1080],
  [390, 844],
  [844, 390],
]) {
  test(`combat fits its modal with a long journal at ${width}x${height}`, async ({ page }) => {
    await page.setViewportSize({ width, height })
    await page.goto('/tests/e2e/fixtures/wasteland-scenes.html')
    await page.getByRole('button', { name: 'Preview combat layout', exact: true }).click()
    const dialog = page.getByRole('dialog')
    const scene = dialog.getByRole('region', { name: 'Desert highway', exact: true })
    await expect(scene).toBeVisible()
    await page.waitForTimeout(150)
    const bounds = (await scene.boundingBox())!
    const space = (await dialog.getByLabel('Battlefield space').boundingBox())!
    const footer = (await dialog
      .getByRole('button', { name: 'Close preview', exact: true })
      .boundingBox())!
    expect(bounds.width).toBeGreaterThan(80)
    expect(bounds.height).toBeGreaterThan(60)
    expect(bounds.x).toBeGreaterThanOrEqual(space.x - 1)
    expect(bounds.y).toBeGreaterThanOrEqual(space.y - 1)
    expect(bounds.x + bounds.width).toBeLessThanOrEqual(space.x + space.width + 1)
    expect(bounds.y + bounds.height).toBeLessThanOrEqual(space.y + space.height + 1)
    expect(bounds.y + bounds.height).toBeLessThanOrEqual(footer.y)
    for (const actor of await scene.locator('.ring-fighter').all()) {
      const actorBounds = (await actor.boundingBox())!
      expect(actorBounds.y).toBeGreaterThanOrEqual(bounds.y + 28)
      expect(actorBounds.y + actorBounds.height).toBeLessThanOrEqual(bounds.y + bounds.height)
    }
    const log = dialog.getByLabel('Battle log', { exact: true })
    await expect(log).toContainText('SKILL')
    await expect(log).toContainText('Turn 1')
    await expect(log).toContainText('Turn 30')
    expect(await log.evaluate((el) => el.scrollHeight > el.clientHeight)).toBe(true)
    if (width >= 1280 && height >= 720) {
      const journal = (await log.boundingBox())!
      expect(journal.width).toBeGreaterThan(300)
      expect(journal.height).toBeGreaterThan(300)
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false)
    await page.screenshot({ path: `test-results/site-combat-fit-${width}-${height}.png` })
  })
}

for (const glow of ['off', 'subtle', 'normal', 'strong']) {
  test(`briefing titles respect ${glow} glow and remain unclipped`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.addInitScript((glow) => localStorage.setItem('visual-effects:glow', glow), glow)
    await page.goto('/tests/e2e/fixtures/wasteland-scenes.html')
    await page.getByRole('combobox', { name: 'Preview location' }).click()
    await page.getByRole('option', { name: 'Arctic research station', exact: true }).click()
    await page.getByRole('button', { name: 'Preview briefing', exact: true }).click()
    const dialog = page.getByRole('dialog')
    const title = dialog.getByRole('heading', { name: 'Arctic research station', exact: true })
    if (glow === 'off') {
      await expect(title).toHaveCSS('text-shadow', 'none')
      await expect(dialog).not.toHaveCSS('box-shadow', /20px/)
    } else {
      await expect(title).not.toHaveCSS('text-shadow', 'none')
    }
    await expect(title).toHaveCSS('overflow', 'visible')
    const bounds = (await title.boundingBox())!
    const frame = (await dialog.boundingBox())!
    expect(bounds.x - frame.x).toBeGreaterThan(20)
    expect(bounds.y - frame.y).toBeGreaterThan(20)
    expect(bounds.x + bounds.width).toBeLessThan(frame.x + frame.width - 20)
    // Same-document preference changes must also reach the teleported header.
    await page.evaluate(() => {
      localStorage.setItem('visual-effects:glow', 'off')
      window.dispatchEvent(
        new StorageEvent('storage', {
          key: 'visual-effects:glow',
          newValue: 'off',
          storageArea: localStorage,
        })
      )
    })
    await expect(title).toHaveCSS('text-shadow', 'none')
    await page.getByRole('button', { name: 'Close', exact: true }).click()
    await expect(dialog).toHaveCount(0)
  })
}

for (const width of [390, 1280]) {
  test(`the encounter scene stays stable while artwork loads at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.route('**/static/**', (route) =>
      route.fulfill({
        path: fileURLToPath(
          new URL(
            '../../../backend/app/static/dweller_thumbnails/base/FOS_Dw_Default_Human_Female.webp',
            import.meta.url
          )
        ),
      })
    )
    let releaseImage: () => void = () => {}
    const imageGate = new Promise<void>((resolve) => {
      releaseImage = resolve
    })
    await page.route('**/assets/wasteland-scenes/**', async (route) => {
      await imageGate
      await route.continue()
    })
    await page.goto('/tests/e2e/fixtures/wasteland-scenes.html', { waitUntil: 'domcontentloaded' })
    const journey = page.getByRole('figure', { name: 'Encounter scene', exact: true })
    await expect(journey).toBeVisible()
    const backdrop = journey.getByAltText('Desert highway')
    const before = await backdrop.boundingBox()
    expect(before).not.toBeNull()
    expect(before!.width / before!.height).toBeCloseTo(50 / 37, 2)
    releaseImage()
    await expect
      .poll(() => backdrop.evaluate((image: HTMLImageElement) => image.naturalWidth))
      .toBeGreaterThan(0)
    const after = await backdrop.boundingBox()
    expect(after!.height).toBeCloseTo(before!.height, 1)
    const actor = journey.getByRole('group', { name: 'Lucy MacLean on expedition' })
    const actorBounds = await actor.boundingBox()
    expect(actorBounds!.height / after!.height).toBeCloseTo(0.44, 2)
    await page.getByRole('combobox', { name: 'Preview location' }).click()
    await page.getByRole('option', { name: 'Subway station', exact: true }).click()
    await expect(journey.getByAltText('Subway station')).toBeVisible()
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > window.innerWidth
    )
    expect(overflow).toBe(false)
    await page.screenshot({ path: `test-results/wasteland-scenes-${width}.png`, fullPage: true })
  })
}

test('failed artwork keeps the encounter caption and explorer visible', async ({ page }) => {
  await page.route('**/assets/wasteland-scenes/**', (route) => route.abort())
  await page.route('**/static/**', (route) => route.abort())
  await page.goto('/tests/e2e/fixtures/wasteland-scenes.html')
  const journey = page.getByRole('figure', { name: 'Encounter scene', exact: true })
  await expect(journey.getByRole('img', { name: 'Desert highway', exact: true })).toBeVisible()
  await expect(journey.getByRole('group', { name: 'Lucy MacLean on expedition' })).toBeVisible()
  await expect(journey.locator('figcaption')).toContainText('Encounter scene')
})

test('the development menu links to the scene preview', async ({ page }) => {
  await page.route('**/api/v1/**', (route) => route.fulfill({ json: {} }))
  await page.route('**/static/**', (route) => route.abort())
  await page.goto('/dev')
  const previewLink = page.getByRole('link', { name: /Wasteland scenes/ })
  await expect(previewLink).toHaveAttribute('href', '/dev/wasteland-scenes')
  await previewLink.click()
  await expect(page.getByRole('heading', { name: 'Wasteland scenes', exact: true })).toBeVisible()
  await expect(page.getByRole('combobox', { name: 'Preview location' })).toBeVisible()
})

for (const width of [390, 1280]) {
  test(`encounter briefing groups health, enemies and journey status at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 })
    await page.goto('/tests/e2e/fixtures/wasteland-scenes.html')
    await page.getByRole('button', { name: 'Preview briefing', exact: true }).click()
    const dialog = page.getByRole('dialog')
    const status = dialog.getByLabel('Encounter status', { exact: true })
    await expect(status).toContainText('HP 81/100')
    await expect(status).toContainText('Radscorpion')
    await expect(status).toContainText('Travel paused')
    await expect(dialog.getByLabel('Encounter briefing', { exact: true })).toBeVisible()
    const health = (await status.getByText('HP 81/100', { exact: true }).boundingBox())!
    const enemies = (await status.getByLabel('Encounter enemies').boundingBox())!
    expect(enemies.x).toBeGreaterThan(health.x + health.width)
    await expect(
      dialog.getByRole('button', { name: 'Close preview', exact: true })
    ).toBeInViewport()
    expect(await dialog.evaluate((el) => el.scrollWidth > el.clientWidth)).toBe(false)
    await page.screenshot({ path: `test-results/site-briefing-${width}.png` })
  })
}

for (const [width, height] of [
  [844, 390],
  [390, 844],
  [1280, 720],
]) {
  test(`paired enemies fit below the scene header at ${width}x${height}`, async ({ page }) => {
    await page.setViewportSize({ width, height })
    await page.goto('/tests/e2e/fixtures/wasteland-scenes.html')
    await page.getByRole('switch', { name: 'Pair of enemies' }).check()
    await page.getByRole('button', { name: 'Preview combat layout', exact: true }).click()
    const scene = page
      .getByRole('dialog')
      .getByRole('region', { name: 'Desert highway', exact: true })
    await expect(scene.getByAltText('Radscorpion 2', { exact: true })).toBeVisible()
    const header = (await scene.getByText('HOSTILES', { exact: true }).locator('..').boundingBox())!
    const frame = (await scene.boundingBox())!
    const fighters = scene.locator('.ring-fighter')
    await expect(fighters).toHaveCount(3)
    for (const fighter of await fighters.all()) {
      const bounds = (await fighter.boundingBox())!
      expect((await fighter.locator('.fighter-meters').boundingBox())!.width).toBeGreaterThan(32)
      expect(bounds.y).toBeGreaterThanOrEqual(header.y + header.height)
      expect(bounds.y + bounds.height).toBeLessThanOrEqual(frame.y + frame.height)
    }
  })
}
