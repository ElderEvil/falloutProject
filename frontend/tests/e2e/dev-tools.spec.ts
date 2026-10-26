import { expect, test } from '@playwright/test'

for (const path of [
  'ui-catalog',
  'animation-gallery',
  'wasteland-scenes',
  'asset-gallery',
  'skill-effects',
]) {
  test(`${path} links back to development tools`, async ({ page }) => {
    await page.goto(`/dev/${path}`)
    const back = page.getByRole('link', { name: 'Back to development tools' })
    await expect(back).toBeVisible()
    await back.click()
    await expect(page).toHaveURL(/\/dev$/)
    await expect(page.getByRole('heading', { name: 'Development tools' })).toBeVisible()
  })
}

test('skill preview plays and can hold the target impact frame', async ({ page }) => {
  await page.goto('/dev/skill-effects')
  await page.getByRole('switch', { name: 'Hold impact frame' }).click()
  await page.getByRole('button', { name: 'Play skill' }).click()
  await expect(page.locator('.skill-hit--stationary')).toBeVisible()
  await expect(page.locator('.skill-hit--stationary')).toHaveCount(1)
})

for (const [weapon, effect] of [
  ['heavy-explosive', 'skill-hit--explosion'],
  ['energy-rifle', 'skill-hit--energy'],
  ['heavy-flamer', 'skill-hit--heat'],
  ['gun-shotgun', 'skill-hit--scatter'],
  ['melee-blunt', 'skill-hit--hammer'],
  ['heavy-automatic', 'skill-hit--automatic'],
] as const) {
  test(`${weapon} selects its skill effect`, async ({ page }) => {
    await page.goto('/dev/skill-effects')
    await page.getByLabel('Weapon skill').selectOption(weapon)
    await page.getByRole('switch', { name: 'Hold impact frame' }).click()
    await page.getByRole('button', { name: 'Play skill' }).click()
    const impact = page.locator(`.${effect}`)
    await expect(impact).toBeVisible()
    if (weapon === 'heavy-explosive') {
      const image = await impact.evaluate((element) => getComputedStyle(element).backgroundImage)
      const url = image.match(/url\("(.+)"\)/)?.[1]
      expect(url).toBeTruthy()
      expect((await page.request.get(url!)).ok()).toBe(true)
    }
  })
}
