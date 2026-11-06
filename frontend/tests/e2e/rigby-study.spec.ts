import { test, expect } from '@playwright/test'

test('equipment, views, and exported rigs remain playable', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('/dev')
  await expect(page.locator('a[href="/dev/dweller-rig"]')).toBeVisible()
  await page.locator('a[href="/dev/dweller-motion-lab"]').click()
  const stage = page.getByTestId('rigby-stage')
  await expect(stage).toHaveAttribute('data-ready', 'true')
  await page.getByRole('button', { name: 'Pause animation' }).click()
  const phase = await stage.getAttribute('data-phase')
  const art = page.getByLabel('Animated dwellers rendered by Rigby2D')
  const before = await art.evaluate((canvas: HTMLCanvasElement) => canvas.toDataURL())
  await page.getByRole('combobox', { name: 'Outfit', exact: true }).click()
  await page.getByRole('option', { name: 'Wasteland vest' }).click()
  await expect(stage).toHaveAttribute('data-phase', phase!)
  expect(await art.evaluate((canvas: HTMLCanvasElement) => canvas.toDataURL())).not.toBe(before)
  for (const [label, choice] of [
    ['Weapon', 'Hunting rifle'],
    ['Headwear', 'Fedora'],
    ['Body profile', 'Bulky humanoid'],
  ]) {
    await page.getByRole('combobox', { name: label, exact: true }).click()
    await page.getByRole('option', { name: choice, exact: true }).click()
  }
  await page.getByRole('button', { name: 'Joints', exact: true }).click()
  await page.getByRole('button', { name: 'Mirror', exact: true }).click()
  await page.getByRole('button', { name: 'Reload exported rig' }).click()
  await expect(page.getByRole('status')).toContainText('Rig serialized and reloaded')
  await expect(stage).toHaveAttribute('data-phase', phase!)
  await page.getByRole('button', { name: 'Walk', exact: true }).click()
  await page.getByRole('button', { name: 'Play animation' }).click()
  await expect.poll(() => stage.getAttribute('data-phase')).not.toBe('0.000')
  await page.getByRole('button', { name: 'Crowd ×36', exact: true }).click()
  await expect(stage).toHaveAttribute('data-mode', 'crowd')
  await expect(page.getByText(/36 actors ·/)).toBeVisible()
  await page.getByRole('button', { name: 'Pause animation' }).click()
  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Rig JSON', exact: true }).click()
  expect((await download).suggestedFilename()).toContain('dweller-quarter-bulky.json')
  expect(errors).toEqual([])
})

test('the study fits a narrow screen and respects reduced motion', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/dev/dweller-motion-lab')
  await expect(page.getByTestId('rigby-stage')).toHaveAttribute('data-ready', 'true')
  await expect(page.getByRole('button', { name: 'Play animation' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true
  )
})
