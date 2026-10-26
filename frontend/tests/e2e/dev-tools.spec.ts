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

for (const [weapon, name, effect] of [
  ['heavy-explosive', 'Blast Wave', 'skill-hit--explosion'],
  ['energy-rifle', 'Beam Sweep', 'skill-hit--energy'],
  ['heavy-flamer', 'Firestorm', 'skill-hit--heat'],
  ['gun-shotgun', 'Scattershot', 'skill-hit--scatter'],
  ['melee-blunt', 'Crushing Blow', 'skill-hit--hammer'],
  ['heavy-automatic', 'Full Auto', 'skill-hit--automatic'],
] as const) {
  test(`${weapon} selects its skill effect`, async ({ page }) => {
    await page.goto('/dev/skill-effects')
    await page.getByRole('combobox', { name: 'Weapon skill' }).click()
    await page.getByRole('option', { name, exact: true }).click()
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
