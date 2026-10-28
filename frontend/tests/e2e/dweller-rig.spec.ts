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

test('keeps original atlas body parts and hangs the open hands from their wrists', async ({
  page,
}) => {
  await page.goto(path)
  await expect(page.locator('[data-part="spine"] image')).toHaveAttribute(
    'href',
    /vault-suit-parts/
  )
  const hands = await page
    .locator('[data-part="frontHand"] image, [data-part="backHand"] image')
    .evaluateAll((images) =>
      images.map((image) => {
        const id = image.closest('[data-part]')!.getAttribute('data-part')!
        const crop = image.parentElement!.getAttribute('viewBox')!.split(' ').map(Number)
        const matrix = (image as SVGGraphicsElement).getScreenCTM()!
        const wrist = new DOMPoint(25, 77).matrixTransform(matrix)
        const fingers = new DOMPoint(65, 82).matrixTransform(matrix)
        const thumb = new DOMPoint(48, 98).matrixTransform(matrix)
        const circle = document
          .querySelector(`[data-joint="${id}"] circle`)!
          .getBoundingClientRect()
        return {
          id,
          containsWrist:
            25 >= crop[0]! &&
            25 <= crop[0]! + crop[2]! &&
            77 >= crop[1]! &&
            77 <= crop[1]! + crop[3]!,
          distance: Math.hypot(
            wrist.x - circle.x - circle.width / 2,
            wrist.y - circle.y - circle.height / 2
          ),
          fingersDown: fingers.y - wrist.y,
          thumbDirection: thumb.x - wrist.x,
        }
      })
    )
  for (const hand of hands) {
    expect(hand.containsWrist).toBe(true)
    expect(hand.distance).toBeLessThan(2)
    expect(hand.fingersDown).toBeGreaterThan(15)
    expect(hand.thumbDirection * (hand.id === 'frontHand' ? 1 : -1)).toBeGreaterThan(5)
  }
})

test('compares the rig with a separately adjustable original-art overlay', async ({ page }) => {
  await page.goto(path)
  await page.getByRole('button', { name: 'Chet overlay off', exact: true }).click()
  const reference = page.locator('[data-reference="chet"]')
  await expect(reference).toHaveAttribute('opacity', '0.4')
  await page.getByRole('slider', { name: 'Reference opacity', exact: true }).focus()
  await page.keyboard.press('End')
  await expect(reference).toHaveAttribute('opacity', '1')
  const gap = await page.evaluate(() => {
    const head = document.querySelector('[data-part="head"] image') as SVGGraphicsElement
    const reference = document.querySelector('[data-reference="chet"] image') as SVGGraphicsElement
    const portraitPoint = new DOMPoint(55, 50).matrixTransform(head.getScreenCTM()!)
    const originalPoint = new DOMPoint(74, 50).matrixTransform(reference.getScreenCTM()!)
    return Math.hypot(portraitPoint.x - originalPoint.x, portraitPoint.y - originalPoint.y)
  })
  expect(gap).toBeLessThan(1)
  await page.getByRole('button', { name: 'Mirror off', exact: true }).click()
  expect(
    await reference.evaluate((el) => (el as SVGGraphicsElement).getScreenCTM()!.a)
  ).toBeLessThan(0)
  await page.getByRole('button', { name: 'Chet overlay on', exact: true }).click()
  await expect(reference).toHaveCount(0)
})

test('seats the original Chet head into the suit neckline through the motion clips', async ({
  page,
}) => {
  await page.goto(path)
  await expect(page.locator('[data-part="head"] image')).toHaveCount(1)
  for (const clip of ['Bind pose', 'Idle', 'Walk', 'Punch']) {
    await page.getByRole('button', { name: clip, exact: true }).click()
    const gap = await page.evaluate(() => {
      const head = document.querySelector('[data-part="head"] image') as SVGGraphicsElement
      const torso = document.querySelector('[data-part="spine"] image') as SVGGraphicsElement
      const neck = new DOMPoint(55, 87).matrixTransform(head.getScreenCTM()!)
      const collar = new DOMPoint(200, 29).matrixTransform(torso.getScreenCTM()!)
      return Math.hypot(neck.x - collar.x, neck.y - collar.y)
    })
    expect(gap).toBeLessThan(2)
  }
  await page.getByText('Original art reference: Chet', { exact: true }).click()
  await expect(
    page.getByAltText('Original Fallout Shelter Chet wearing his Vault 33 suit')
  ).toBeVisible()
})

test('keeps the resized shoes attached at the native ankle points', async ({ page }) => {
  await page.goto(path)
  await expect(page.locator('[data-part="frontFoot"] image')).toHaveCount(1)
  const gaps = await page
    .locator('[data-part="frontFoot"] image, [data-part="backFoot"] image')
    .evaluateAll((images) =>
      images.map((image) => {
        const id = image.closest('[data-part]')!.getAttribute('data-part')!
        const ankle = new DOMPoint(id === 'frontFoot' ? 487 : 414, 220).matrixTransform(
          (image as SVGGraphicsElement).getScreenCTM()!
        )
        const circle = document
          .querySelector(`[data-joint="${id}"] circle`)!
          .getBoundingClientRect()
        return Math.hypot(
          ankle.x - circle.x - circle.width / 2,
          ankle.y - circle.y - circle.height / 2
        )
      })
    )
  for (const gap of gaps) expect(gap).toBeLessThan(1)
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
