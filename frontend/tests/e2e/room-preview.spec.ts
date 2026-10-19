import { test, expect } from '@playwright/test'

test('room preview dweller icons sit slightly above the bottom edge', async ({ page }) => {
  await page.goto('/tests/e2e/fixtures/room-preview.html')
  const lift = await page.locator('.dweller-sprites-overlay').evaluate((overlay) => {
    const frame = overlay.closest('.room-image-container')!
    const overlayBounds = overlay.getBoundingClientRect()
    const frameBounds = frame.getBoundingClientRect()
    const baseline = parseFloat(getComputedStyle(document.documentElement).fontSize) / 2
    return (frameBounds.bottom - overlayBounds.bottom - baseline) / frameBounds.height
  })
  expect(lift).toBeGreaterThanOrEqual(0.05)
  expect(lift).toBeLessThanOrEqual(0.1)
})

test('room preview portraits preserve their image aspect ratio', async ({ page }) => {
  await page.goto('/tests/e2e/fixtures/room-preview.html?portrait=1')
  const portrait = page.locator('.scene-dweller-portrait').first()
  await expect(portrait).toBeVisible()
  await expect(portrait).toHaveCSS('object-fit', 'contain')
  const aspectRatio = await portrait.evaluate(
    (image: HTMLImageElement) => image.naturalWidth / image.naturalHeight
  )
  expect(aspectRatio).toBeLessThan(1)
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
    for (const name of ['Open Ada Worker', 'Open Ash Apprentice']) {
      const portrait = page.getByRole('button', { name, exact: true })
      await expect(portrait).toHaveCSS('width', '64px')
      await expect(portrait).toHaveCSS('height', '64px')
    }
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
