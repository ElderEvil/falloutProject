import { expect, test } from '@playwright/test'

for (const width of [390, 1280]) {
  test(`all skill icons render in meters, preview and journal at ${width}px`, async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width, height: 1000 })
    await page.goto('/tests/e2e/fixtures/skill-icons.html', { waitUntil: 'domcontentloaded' })
    const catalog = page.getByRole('region', { name: 'Skill icon catalog' })
    await expect(catalog.getByRole('article')).toHaveCount(12)
    const meterIcons = catalog.locator('button [data-skill-icon]')
    await expect(meterIcons).toHaveCount(12)
    for (const icon of await meterIcons.all()) {
      await expect(icon).toBeVisible()
      const bounds = (await icon.boundingBox())!
      expect(bounds.width).toBeGreaterThanOrEqual(14)
      expect(bounds.height).toBeGreaterThanOrEqual(14)
    }
    const glyphs = await meterIcons.evaluateAll((nodes) => nodes.map((node) => node.innerHTML))
    expect(new Set(glyphs).size).toBe(12)
    const activate = page.getByRole('button', { name: 'Use Aimed Shot from Lucy on Cooper' })
    await expect(activate.locator('[data-skill-icon="gun-rifle"]')).toBeVisible()
    await activate.scrollIntoViewIfNeeded()
    await activate.hover()
    await expect(
      page.locator('[data-slot="tooltip-content"] [data-skill-icon="gun-rifle"]')
    ).toBeVisible()
    await page.getByLabel('Battle journal').locator('summary').click()
    await expect(page.getByLabel('Battle log').locator('[data-skill-icon]')).toHaveCount(12)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: testInfo.outputPath(`skill-icons-${width}.png`), fullPage: true })
  })
}

test('skill icons remain visible with reduced motion and without external image requests', async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  const images: string[] = []
  page.on('request', (request) => {
    if (request.resourceType() === 'image') images.push(request.url())
  })
  await page.goto('/tests/e2e/fixtures/skill-icons.html', { waitUntil: 'domcontentloaded' })
  const catalog = page.getByRole('region', { name: 'Skill icon catalog' })
  await expect(catalog.locator('button [data-skill-icon]')).toHaveCount(12)
  await expect(catalog.getByRole('button').first()).toHaveCSS('animation-name', 'none')
  await expect(catalog.locator('[data-skill-icon="unarmed"]').first()).toBeVisible()
  expect(images).toEqual([])
})
