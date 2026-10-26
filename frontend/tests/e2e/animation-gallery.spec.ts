import { expect, test } from '@playwright/test'
import { setAuthToken, TEST_USER } from './fixtures/auth'

test('inspects poses, edits playback order, and plays the shared rush animation', async ({
  page,
}) => {
  await page.goto('/dev/animation-gallery')
  await expect(page.getByRole('heading', { name: 'Animation Gallery', exact: true })).toBeVisible()
  const success = page.getByRole('region', { name: 'Rush success', exact: true })
  const failure = page.getByRole('region', { name: 'Rush failure', exact: true })
  await expect(success.getByRole('button', { name: 'Play', exact: true })).toBeVisible()
  await expect(success.getByLabel('Playback steps').getByRole('button')).toHaveCount(7)
  await expect(failure.getByRole('button', { name: 'Play', exact: true })).toBeVisible()

  await expect(
    success.getByRole('group', { name: 'Source pose 6', exact: true }).locator('svg').first()
  ).toHaveCSS('height', '80px')
  await success.getByRole('button', { name: 'Inspect pose 6', exact: true }).click()
  await expect(success.getByText('Pose 6 · Source pose', { exact: true })).toBeVisible()

  await success.getByLabel('Pose order').fill('0, 1, 2')
  await success.getByRole('button', { name: 'Apply order', exact: true }).click()
  await expect(success.getByText('Pose 0 · Step 1 / 3', { exact: true })).toBeVisible()
  await success.getByRole('button', { name: 'Next', exact: true }).click()
  await expect(success.getByText('Pose 1 · Step 2 / 3', { exact: true })).toBeVisible()
  await success.getByRole('button', { name: 'Previous', exact: true }).click()
  await expect(success.getByText('Pose 0 · Step 1 / 3', { exact: true })).toBeVisible()

  await success.getByLabel('Pose order').fill('0, 9')
  await success.getByRole('button', { name: 'Apply order', exact: true }).click()
  await expect(success.getByRole('alert')).toContainText('pose numbers from 0 to 6')
  await expect(success.getByText('Pose 0 · Step 1 / 3', { exact: true })).toBeVisible()
  await success.getByRole('button', { name: 'Reset order' }).click()
  await expect(success.getByRole('alert')).toHaveCount(0)
  await expect(success.getByText('Pose 4 · Step 1 / 7', { exact: true })).toBeVisible()

  await success.getByRole('button', { name: 'Play', exact: true }).click()
  await expect(success.getByText('Playing', { exact: true })).toBeVisible()
  await expect(success.getByText('Pose 4 · Step 1 / 7', { exact: true })).not.toBeVisible()
  await success.getByRole('button', { name: 'Pause', exact: true }).click()
  await expect(success.getByText('Paused', { exact: true })).toBeVisible()
  await success.getByRole('button', { name: 'Play', exact: true }).click()
  await expect(success.getByText('Pose 6 · Step 7 / 7', { exact: true })).toBeVisible()
  await expect(success.getByText('Paused', { exact: true })).toBeVisible()
  await expect(failure.getByText('Pose 2 · Step 1 / 7', { exact: true })).toBeVisible()

  await expect(page.getByRole('img', { name: /sprite sheet$/ })).toHaveCount(9)
  for (const image of await page.getByRole('img', { name: /sprite sheet$/ }).all()) {
    await image.scrollIntoViewIfNeeded()
    await expect
      .poll(() => image.evaluate((element) => (element as HTMLImageElement).naturalWidth))
      .toBe(Number(await image.getAttribute('width')))
  }
})

test('links from the dev index and fits a phone viewport', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/dev/')
  await page.getByRole('link', { name: /Animation gallery/ }).click()
  await expect(page).toHaveURL(/\/dev\/animation-gallery$/)
  await expect(page.getByRole('heading', { name: 'Animation Gallery', exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true
  )
})

test('plays each additional Vault Boy gesture once and holds its final pose', async ({ page }) => {
  await page.clock.install()
  await page.goto('/dev/animation-gallery')
  const animations = [
    { title: 'Baby announcement', steps: 7, finalPose: 1, file: 'Baby' },
    { title: 'All good', steps: 7, finalPose: 5, file: 'Ok' },
    { title: 'Low food', steps: 7, finalPose: 3, file: 'FoodLow' },
    { title: 'Low water', steps: 6, finalPose: 4, file: 'WaterLow' },
    { title: 'Low power', steps: 7, finalPose: 2, file: 'PowerLow' },
    { title: 'Low happiness', steps: 7, finalPose: 3, file: 'HappynessLow' },
    { title: 'Storage full', steps: 8, finalPose: 3, file: 'Storage' },
  ]
  for (const animation of animations) {
    const preview = page.getByRole('region', { name: animation.title, exact: true })
    const steps = preview.getByLabel('Playback steps').getByRole('button')
    await expect(steps).toHaveCount(animation.steps)
    const poses = await steps.allTextContents()
    expect(new Set(poses).size).toBe(animation.steps)
    await expect(preview.locator('svg image').first()).toHaveAttribute(
      'href',
      `/assets/vault-boy/VaultBoy_Animations${animation.file}.webp`
    )
    await preview.getByRole('button', { name: 'Play', exact: true }).click()
    await page.clock.runFor(2000)
    const final = preview.getByText(
      `Pose ${animation.finalPose} · Step ${animation.steps} / ${animation.steps}`,
      { exact: true }
    )
    await expect(final).toBeVisible()
    await expect(preview.getByText('Paused', { exact: true })).toBeVisible()
    await page.clock.runFor(1000)
    await expect(final).toBeVisible()
  }
})

test('dev index lists all menus without gallery cross-links', async ({ page }) => {
  await page.goto('/dev/')
  const menus = page.getByRole('navigation', { name: 'Development menus' })
  await expect(menus.getByRole('link')).toHaveCount(4)
  await expect(menus.getByRole('link', { name: /Wasteland scenes/ })).toHaveAttribute(
    'href',
    '/dev/wasteland-scenes'
  )
  await expect(menus.getByRole('link', { name: /UI catalog/ })).toHaveAttribute(
    'href',
    '/dev/ui-catalog'
  )
  await menus.getByRole('link', { name: /Asset gallery/ }).click()
  await expect(page.getByRole('link', { name: /Animation gallery/ })).toHaveCount(0)
  await page.goto('/dev/animation-gallery')
  await expect(page.getByRole('link', { name: /Asset gallery/ })).toHaveCount(0)
})

for (const viewport of [
  { width: 1280, height: 900 },
  { width: 375, height: 812 },
]) {
  test(`corner feedback fits ${viewport.width}px and respects reduced motion`, async ({ page }) => {
    await page.setViewportSize(viewport)
    await page.goto('/dev/animation-gallery')
    const food = page.getByRole('region', { name: 'Low food', exact: true })
    await food.getByRole('button', { name: 'Show in corner', exact: true }).click()
    const overlay = page.locator('.vault-boy-feedback')
    await expect(overlay).toBeVisible()
    await expect(overlay).toHaveCSS('pointer-events', 'none')
    await expect(overlay).toHaveCSS('transform', 'none')
    const bounds = await overlay.boundingBox()
    expect(bounds).not.toBeNull()
    expect(viewport.width - bounds!.x - bounds!.width).toBeCloseTo(16, 0)
    expect(viewport.height - bounds!.y - bounds!.height).toBeCloseTo(80, 0)
    await overlay.getByRole('button', { name: 'Dismiss animation' }).click()
    await expect(overlay).not.toBeVisible()
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await food.getByRole('button', { name: 'Show in corner', exact: true }).click()
    await expect(overlay.locator(':scope > svg > svg')).toHaveAttribute(
      'viewBox',
      '1314 116 391 465'
    )
    await overlay.getByRole('button', { name: 'Dismiss animation' }).click()
  })
}

for (const scenario of [
  { warning: 'low_food', sheet: 'VaultBoy_AnimationsFoodLow.webp' },
  { warning: 'low_water', sheet: 'VaultBoy_AnimationsWaterLow.webp' },
  { warning: 'low_power', sheet: 'VaultBoy_AnimationsPowerLow.webp' },
  { warning: 'happiness', sheet: 'VaultBoy_AnimationsHappynessLow.webp' },
]) {
  test(`shows ${scenario.warning} feedback inside the actual vault`, async ({ page }) => {
    const vault = {
      id: 'vault-1',
      number: 42,
      bottle_caps: 1000,
      happiness: scenario.warning === 'happiness' ? 40 : 80,
      power: 80,
      power_max: 100,
      food: 80,
      food_max: 100,
      water: 80,
      water_max: 100,
      population_max: 10,
      dweller_count: 0,
      room_count: 0,
      stimpack: 0,
      radaway: 0,
      resource_warnings:
        scenario.warning === 'happiness'
          ? []
          : [{ type: scenario.warning, message: 'Production needs attention.' }],
    }
    await page.route('**/api/v1/**', async (route) => {
      const path = new URL(route.request().url()).pathname
      if (path === '/api/v1/users/me') return route.fulfill({ json: TEST_USER })
      if (path === '/api/v1/vaults/my') return route.fulfill({ json: [vault] })
      if (path === '/api/v1/vaults/vault-1') return route.fulfill({ json: vault })
      if (path === '/api/v1/notifications/unread-count')
        return route.fulfill({ json: { count: 0 } })
      if (path.startsWith('/api/v1/stream/')) {
        return route.fulfill({ contentType: 'text/event-stream', body: ': connected\n\n' })
      }
      return route.fulfill({ json: [] })
    })
    await page.goto('/login')
    await setAuthToken(page, 'local-animation-test')
    await page.goto('/vault/vault-1')
    const overlay = page.locator('.vault-boy-feedback')
    await expect(overlay).toBeVisible()
    await expect(overlay.locator('image')).toHaveAttribute(
      'href',
      `/assets/vault-boy/${scenario.sheet}`
    )
    await expect(overlay).toContainText(
      scenario.warning === 'happiness' ? 'Happiness is low' : 'Production needs attention.'
    )
    await overlay.getByRole('button', { name: 'Dismiss animation' }).click()
    await expect(overlay).not.toBeVisible()
  })
}
