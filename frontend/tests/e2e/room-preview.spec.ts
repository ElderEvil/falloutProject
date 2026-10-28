import { test, expect } from '@playwright/test'

test('room preview dweller icons sit slightly above the bottom edge', async ({ page }) => {
  await page.goto('/tests/e2e/fixtures/room-preview.html')
  const lift = await page.locator('.dweller-sprites-overlay').evaluate((overlay) => {
    const frame = overlay.closest('.room-image-frame')!
    const overlayBounds = overlay.getBoundingClientRect()
    const frameBounds = frame.getBoundingClientRect()
    const baseline = parseFloat(getComputedStyle(document.documentElement).fontSize) / 2
    return (frameBounds.bottom - overlayBounds.bottom - baseline) / frameBounds.height
  })
  expect(lift).toBeGreaterThanOrEqual(0.05)
  expect(lift).toBeLessThanOrEqual(0.1)
})

test('room preview portraits keep their aspect ratio and size over the room background', async ({
  page,
}) => {
  await page.goto('/tests/e2e/fixtures/room-preview.html?portrait=1')
  const portrait = page.locator('.scene-dweller-portrait').first()
  await expect(portrait).toBeVisible()
  await expect(portrait).toHaveCSS('object-fit', 'contain')
  await expect
    .poll(() => portrait.evaluate((image: HTMLImageElement) => image.naturalWidth))
    .toBeGreaterThan(0)
  const slot = portrait.locator('..')
  await expect(slot).toHaveCSS('background-color', 'rgba(0, 0, 0, 0)')
  await expect(slot).toHaveCSS('border-top-width', '0px')
  const proportions = await portrait.evaluate((image: HTMLImageElement) => {
    const bounds = image.getBoundingClientRect()
    const slotBounds = image.closest('button')!.getBoundingClientRect()
    return {
      source: image.naturalWidth / image.naturalHeight,
      rendered: bounds.width / bounds.height,
      slot: slotBounds.width / slotBounds.height,
      centered: Math.abs(bounds.x + bounds.width / 2 - slotBounds.x - slotBounds.width / 2),
      slotScale: slotBounds.height / 64,
      renderedHeight: bounds.height,
    }
  })
  expect(proportions.source).toBeLessThan(1)
  expect(proportions.rendered).toBeCloseTo(proportions.source, 2)
  expect(proportions.slot).toBeCloseTo(proportions.source, 2)
  expect(proportions.centered).toBeLessThan(1)
  expect(proportions.slotScale).toBeGreaterThan(1)
  const containment = await page.evaluate(() => {
    const overlay = document.querySelector('.dweller-sprites-overlay')!
    const frame = overlay.closest('.room-image-frame')!
    const overlayBounds = overlay.getBoundingClientRect()
    const frameBounds = frame.getBoundingClientRect()
    return {
      left: overlayBounds.left - frameBounds.left,
      right: frameBounds.right - overlayBounds.right,
      top: overlayBounds.top - frameBounds.top,
      bottom: frameBounds.bottom - overlayBounds.bottom,
    }
  })
  expect(containment.left).toBeGreaterThanOrEqual(0)
  expect(containment.right).toBeGreaterThanOrEqual(0)
  expect(containment.top).toBeGreaterThanOrEqual(0)
  expect(containment.bottom).toBeGreaterThanOrEqual(0)
  const portraitHeight = proportions.renderedHeight
  const emptySlot = page.locator('.scene-empty-worker').first()
  const emptySlotBounds = await emptySlot.evaluate((slot) => {
    const bounds = slot.getBoundingClientRect()
    return { width: bounds.width, height: bounds.height }
  })
  expect(emptySlotBounds.width / emptySlotBounds.height).toBeCloseTo(proportions.source, 2)
  expect(emptySlotBounds.height).toBeCloseTo(portraitHeight, 0)
  const emptyIcon = emptySlot.locator('.empty-dweller-silhouette')
  await expect(emptyIcon).toBeVisible()
  await expect(emptyIcon).toHaveAttribute('aria-hidden', 'true')
  const emptyIconBounds = await emptyIcon.evaluate((icon) => {
    const bounds = icon.getBoundingClientRect()
    return { ratio: bounds.width / bounds.height, height: bounds.height }
  })
  expect(emptyIconBounds.ratio).toBeLessThan(1)
  expect(emptyIconBounds.height).toBeLessThan(emptySlotBounds.height)
  const fallback = page.locator('.scene-dweller .scene-dweller-icon').first()
  await expect(fallback).toBeVisible()
  const fallbackBounds = await fallback.evaluate((icon) => {
    const bounds = icon.getBoundingClientRect()
    const slot = icon.closest('button')!.getBoundingClientRect()
    return {
      height: bounds.height,
      ratio: bounds.width / bounds.height,
      slotRatio: slot.width / slot.height,
    }
  })
  expect(fallbackBounds.height).toBeLessThanOrEqual(portraitHeight)
  expect(fallbackBounds.ratio).toBeCloseTo(proportions.source, 2)
  expect(fallbackBounds.slotRatio).toBeCloseTo(proportions.source, 2)
})

test('room preview renders the equipped pet beside its dweller', async ({ page }) => {
  await page.goto('/tests/e2e/fixtures/room-preview.html?pet=1')
  const pet = page.locator('.combat-pet').first()
  await expect(pet).toBeVisible()
  await expect(pet.locator('img')).toHaveAttribute('alt', /Dogmeat/)

  const petBounds = await pet.evaluate((element) => {
    const bounds = element.getBoundingClientRect()
    return {
      width: bounds.width,
      height: bounds.height,
      bottom: bounds.bottom,
      right: bounds.right,
    }
  })
  const worker = page.getByRole('button', { name: 'Open Ada Worker', exact: true })
  const workerBounds = await worker.evaluate((element) => {
    const bounds = element.getBoundingClientRect()
    return { height: bounds.height, bottom: bounds.bottom, left: bounds.left }
  })
  expect(petBounds.right).toBeLessThanOrEqual(workerBounds.left + 0.1)
  expect(petBounds.height).toBeLessThan(workerBounds.height)
  expect(petBounds.width / petBounds.height).toBeCloseTo(1.5, 1)
  expect(Math.abs(petBounds.bottom - workerBounds.bottom)).toBeLessThanOrEqual(2)
  await worker.hover()
  await page.getByRole('button', { name: 'Unassign Ada Worker', exact: true }).click()
  await expect(worker).toHaveCount(0)
})

test('room preview shows a silhouette when a thumbnail fails to load', async ({ page }) => {
  await page.goto('/tests/e2e/fixtures/room-preview.html?broken=1')
  const worker = page.getByRole('button', { name: 'Open Ada Worker', exact: true })
  await expect(worker.locator('img')).toHaveCount(0)
  const fallback = worker.locator('.scene-dweller-icon')
  await expect(fallback).toBeVisible()
  const fallbackRatio = await fallback.evaluate((icon) => {
    const bounds = icon.getBoundingClientRect()
    return bounds.width / bounds.height
  })
  expect(fallbackRatio).toBeCloseTo(2 / 3, 2)
})

test('touch users see unassign controls for workers and apprentices', async ({ browser }) => {
  const context = await browser.newContext({
    isMobile: true,
    hasTouch: true,
    viewport: { width: 390, height: 844 },
  })
  const page = await context.newPage()
  try {
    await page.goto('http://localhost:5173/tests/e2e/fixtures/room-preview.html')
    const worker = page.getByRole('button', { name: 'Unassign Ada Worker', exact: true })
    const apprentice = page.getByRole('button', { name: 'Unassign Ash Apprentice', exact: true })
    await expect(worker).toHaveCSS('opacity', '1')
    await expect(apprentice).toHaveCSS('opacity', '1')
    const buttonSizes: Array<{ width: number; height: number }> = []
    for (const name of ['Open Ada Worker', 'Open Ash Apprentice']) {
      const portrait = page.getByRole('button', { name, exact: true })
      buttonSizes.push(
        await portrait.evaluate((element) => {
          const bounds = element.getBoundingClientRect()
          return { width: bounds.width, height: bounds.height }
        })
      )
    }
    expect(buttonSizes[0]!.width / buttonSizes[0]!.height).toBeCloseTo(2 / 3, 2)
    expect(buttonSizes[0]!.height).toBeGreaterThan(100)
    expect(buttonSizes[1]).toEqual(buttonSizes[0])
    await worker.tap()
    await expect(page.getByRole('button', { name: 'Assign worker', exact: true })).toHaveCount(2)
    await apprentice.tap()
    await expect(
      page.getByRole('button', { name: 'Assign child or teen apprentice to this slot' })
    ).toBeVisible()
  } finally {
    await context.close()
  }
})

test('desktop unassign controls appear on hover and keyboard focus', async ({ page }) => {
  await page.goto('/tests/e2e/fixtures/room-preview.html')
  const worker = page.getByRole('button', { name: 'Unassign Ada Worker', exact: true })
  await expect(worker).toHaveCSS('opacity', '0')
  await page.getByRole('button', { name: 'Open Ada Worker', exact: true }).hover()
  await expect(worker).toHaveCSS('opacity', '1')
  await page.mouse.move(0, 0)
  await expect(worker).toHaveCSS('opacity', '0')
  await worker.focus()
  await expect(worker).toHaveCSS('opacity', '1')
  await page.keyboard.press('Enter')
  await expect(page.getByRole('button', { name: 'Open Ada Worker', exact: true })).toHaveCount(0)
})

test('small room avatars keep the pet, apprentice badge and level readable', async ({ page }) => {
  await page.goto('/tests/e2e/fixtures/room-preview.html?pet=1&grid=1')
  const avatar = page.getByRole('group', {
    name: 'Ada Worker (Lv50), apprentice in Strength, pet Dogmeat',
    exact: true,
  })
  const geometry = await avatar.evaluate((element) => {
    const bounds = element.getBoundingClientRect()
    const pet = element.querySelector('.dweller-pet')!.getBoundingClientRect()
    const level = element.querySelector('.dweller-level')!.getBoundingClientRect()
    const apprentice = element.querySelector('.apprentice-badge')!.getBoundingClientRect()
    return {
      width: bounds.width,
      petBottom: pet.bottom,
      levelTop: level.top,
      petRight: pet.right,
      apprenticeLeft: apprentice.left,
    }
  })
  expect(geometry.width).toBe(28)
  expect(geometry.petBottom).toBeLessThanOrEqual(geometry.levelTop)
  expect(geometry.petRight).toBeLessThanOrEqual(geometry.apprenticeLeft)
})

for (const width of [390, 1280]) {
  test(`pets stay inside full room previews at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/tests/e2e/fixtures/room-preview.html?pet=1&full=1')
    const layout = await page.locator('.dweller-sprites-overlay').evaluate((overlay) => {
      const frame = overlay.parentElement!.getBoundingClientRect()
      const portraits = [...overlay.querySelectorAll('.scene-dweller')].map((el) =>
        el.getBoundingClientRect()
      )
      const pets = [...overlay.querySelectorAll('.combat-pet')].map((el) =>
        el.getBoundingClientRect()
      )
      return pets.map((pet, i) => ({
        left: pet.left,
        right: pet.right,
        frameRight: frame.right,
        frameLeft: frame.left,
        previousRight: i ? portraits[i - 1]!.right : frame.left,
      }))
    })
    expect(layout).toHaveLength(6)
    for (const pet of layout) {
      expect(pet.right).toBeLessThanOrEqual(pet.frameRight + 0.1)
      expect(pet.left).toBeGreaterThanOrEqual(pet.frameLeft - 0.1)
      expect(pet.left).toBeGreaterThanOrEqual(pet.previousRight - 0.1)
    }
  })
}
