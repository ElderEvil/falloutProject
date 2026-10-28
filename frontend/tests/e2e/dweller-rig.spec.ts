import { test, expect } from '@playwright/test'

const path = '/dev/dweller-rig'

test('inspects the skeleton and propagates a shoulder edit to attached parts', async ({ page }) => {
  await page.goto(path)
  await expect(page.getByRole('heading', { name: 'Dweller rig', exact: true })).toBeVisible()
  await expect(page.locator('[data-bone]')).toHaveCount(15)
  const forearm = page.locator('[data-part="frontForearm"]')
  const opposite = page.locator('[data-part="backForearm"]')
  const before = await forearm.getAttribute('transform')
  const oppositeBefore = await opposite.getAttribute('transform')
  await page.getByRole('slider', { name: 'Joint angle adjustment', exact: true }).focus()
  await page.keyboard.press('End')
  await expect(forearm).not.toHaveAttribute('transform', before!)
  await expect(opposite).toHaveAttribute('transform', oppositeBefore!)
  await page.getByRole('button', { name: 'Reset pose', exact: true }).click()
  await expect(forearm).toHaveAttribute('transform', before!)
  await page.getByRole('button', { name: 'Select Head', exact: true }).focus()
  await page.keyboard.press('Enter')
  await expect(page.getByLabel('Selected joint')).toContainText('Head')
  await expect(page.getByText('Parent → Spine', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'bones', exact: true }).click()
  await expect(page.locator('[data-part]')).toHaveCount(0)
  await expect(page.locator('[data-bone]')).toHaveCount(15)
})

test('scrubs, steps, plays and pauses an articulated walk without changing the stage frame', async ({
  page,
}) => {
  await page.goto(path)
  const stage = page.getByRole('region', { name: 'Rig stage', exact: true })
  const size = await stage.boundingBox()
  await page.getByRole('button', { name: 'Walk', exact: true }).click()
  await page.getByRole('button', { name: 'Next frame', exact: true }).click()
  await expect(page.getByLabel('Clip progress')).not.toHaveText('0%')
  await page.getByRole('slider', { name: 'Clip timeline', exact: true }).focus()
  await page.keyboard.press('Home')
  await expect(page.getByLabel('Clip progress')).toHaveText('0%')
  await page.getByRole('button', { name: 'Play', exact: true }).click()
  await expect(page.getByLabel('Clip progress')).not.toHaveText('0%')
  await page.getByRole('button', { name: 'Pause', exact: true }).click()
  const paused = await page.getByLabel('Clip progress').textContent()
  await page.waitForTimeout(160)
  await expect(page.getByLabel('Clip progress')).toHaveText(paused!)
  const after = await stage.boundingBox()
  expect(after!.height).toBe(size!.height)
  expect(after!.width).toBe(size!.width)
  await page.getByRole('button', { name: 'Mirror off', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Mirror on', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true'
  )
})

test('starts paused with reduced motion and is discoverable from the dev menu', async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/dev')
  await page.getByRole('link', { name: /Dweller rig/ }).click()
  await expect(page).toHaveURL(/\/dev\/dweller-rig$/)
  await expect(page.getByText('Reduced motion detected.', { exact: false })).toBeVisible()
  await page.getByRole('button', { name: 'Punch', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Play', exact: true })).toBeVisible()
  await expect(page.getByLabel('Clip progress')).toHaveText('0%')
})

test('aligns left-facing outfit cutouts with the right-facing portrait, including mirroring', async ({
  page,
}) => {
  await page.goto(path)
  const direction = (part: string) =>
    page
      .locator(`[data-part="${part}"] image`)
      .evaluate((image) => (image as SVGGraphicsElement).getScreenCTM()!.a)
  for (const part of ['spine', 'frontFoot', 'backFoot'])
    expect(await direction(part)).toBeLessThan(0)
  expect(await direction('head')).toBeGreaterThan(0)
  await page.getByRole('button', { name: 'Mirror off', exact: true }).click()
  for (const part of ['spine', 'frontFoot', 'backFoot'])
    expect(await direction(part)).toBeGreaterThan(0)
  expect(await direction('head')).toBeLessThan(0)
})

test('keeps each hand wrist attached to its joint with opposite front/back handedness', async ({
  page,
}) => {
  await page.goto(path)
  await expect(page.locator('[data-part$="Hand"] image')).toHaveCount(2)
  const hands = await page
    .locator('[data-part="frontHand"] image, [data-part="backHand"] image')
    .evaluateAll((images) =>
      images.map((image) => {
        const id = image.closest('[data-part]')!.getAttribute('data-part')!
        const matrix = (image as SVGGraphicsElement).getScreenCTM()!
        // Wrist attachment in the original accessories atlas, before cropping/scaling.
        const wrist = new DOMPoint(145, 35).matrixTransform(matrix)
        const circle = document
          .querySelector(`[data-joint="${id}"] circle`)!
          .getBoundingClientRect()
        return {
          id,
          distance: Math.hypot(
            wrist.x - circle.x - circle.width / 2,
            wrist.y - circle.y - circle.height / 2
          ),
          handedness: matrix.a * matrix.d - matrix.b * matrix.c,
        }
      })
    )
  expect(hands).toHaveLength(2)
  for (const hand of hands) expect(hand.distance).toBeLessThan(2)
  expect(hands.find((hand) => hand.id === 'frontHand')!.handedness).toBeLessThan(0)
  expect(hands.find((hand) => hand.id === 'backHand')!.handedness).toBeGreaterThan(0)
})
