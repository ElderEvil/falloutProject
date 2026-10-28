import { test, expect } from '@playwright/test'
import outlines from './dweller-rig-outlines.json' with { type: 'json' }

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
    // Preserve thumb direction; hand size is checked against reference pixels below.
    expect(hand.thumbDirection * (hand.id === 'frontHand' ? 1 : -1)).toBeGreaterThan(0)
  }
})

test('positions both open wrists against Chet’s hand outlines', async ({ page }) => {
  await page.goto(path)
  await page.getByRole('button', { name: 'Chet overlay off', exact: true }).click()
  const gaps = await page.evaluate(() => {
    const reference = document.querySelector('[data-reference="chet"] image') as SVGGraphicsElement
    return [
      { id: 'frontHand', target: [20, 186] },
      { id: 'backHand', target: [120, 179] },
    ].map(({ id, target }) => {
      const hand = document.querySelector(`[data-part="${id}"] image`) as SVGGraphicsElement
      const toReference = reference.getScreenCTM()!.inverse().multiply(hand.getScreenCTM()!)
      const wrist = new DOMPoint(25, 77).matrixTransform(toReference)
      return Math.hypot(wrist.x - target[0]!, wrist.y - target[1]!)
    })
  })
  for (const gap of gaps) expect(gap).toBeLessThan(1)
})

test('keeps the left hand artwork within Chet’s portrait frame', async ({ page }) => {
  await page.goto(path)
  await page.getByRole('button', { name: 'Chet overlay off', exact: true }).click()
  const rightEdge = await page.evaluate(async () => {
    const hand = document.querySelector('[data-part="backHand"] image') as SVGGraphicsElement
    const reference = document.querySelector('[data-reference="chet"] image') as SVGGraphicsElement
    const toReference = reference.getScreenCTM()!.inverse().multiply(hand.getScreenCTM()!)
    const source = new Image()
    source.src = hand.getAttribute('href')!
    await source.decode()
    const canvas = document.createElement('canvas')
    canvas.width = source.width
    canvas.height = source.height
    const context = canvas.getContext('2d')!
    context.drawImage(source, 0, 0)
    const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data
    const [x, y, width, height] = hand
      .parentElement!.getAttribute('viewBox')!
      .split(' ')
      .map(Number) as [number, number, number, number]
    let edge = -Infinity
    for (let row = y; row < y + height; row++) {
      for (let column = x; column < x + width; column++) {
        if (pixels[(row * canvas.width + column) * 4 + 3]! < 200) continue
        edge = Math.max(edge, new DOMPoint(column + 0.5, row + 0.5).matrixTransform(toReference).x)
      }
    }
    return edge
  })
  expect(rightEdge).toBeGreaterThan(125)
  expect(rightEdge).toBeLessThan(136)
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

test('extracts the head without the outfit fragment beside the chin', async ({ page }) => {
  await page.goto(path)
  const alpha = await page.locator('[data-part="head"] image').evaluate(async (element) => {
    const source = new Image()
    source.src = element.getAttribute('href')!
    await source.decode()
    const canvas = document.createElement('canvas')
    canvas.width = 94
    canvas.height = 96
    const context = canvas.getContext('2d')!
    context.drawImage(source, 0, 0)
    const image = element.cloneNode(true) as SVGImageElement
    image.setAttribute('href', canvas.toDataURL())
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
    svg.setAttribute('width', '94')
    svg.setAttribute('height', '96')
    svg.append(element.closest('svg[aria-label]')!.querySelector('defs')!.cloneNode(true), image)
    const rendered = new Image()
    rendered.src = `data:image/svg+xml,${encodeURIComponent(new XMLSerializer().serializeToString(svg))}`
    await rendered.decode()
    context.clearRect(0, 0, 94, 96)
    context.drawImage(rendered, 0, 0)
    return {
      cheek: context.getImageData(70, 75, 1, 1).data[3],
      chin: context.getImageData(65, 86, 1, 1).data[3],
      collar: context.getImageData(76, 92, 1, 1).data[3],
    }
  })
  expect(alpha.cheek).toBeGreaterThan(200)
  expect(alpha.chin).toBeGreaterThan(200)
  expect(alpha.collar).toBe(0)
})

test('keeps the head and calibrated torso attachment stable through the motion clips', async ({
  page,
}) => {
  await page.goto(path)
  await expect(page.locator('[data-part="head"] image')).toHaveCount(1)
  let bindGap: number | undefined
  for (const clip of ['Bind pose', 'Idle', 'Walk', 'Punch']) {
    await page.getByRole('button', { name: clip, exact: true }).click()
    const gap = await page.evaluate(() => {
      const head = document.querySelector('[data-part="head"] image') as SVGGraphicsElement
      const torso = document.querySelector('[data-part="spine"] image') as SVGGraphicsElement
      const neck = new DOMPoint(55, 87).matrixTransform(head.getScreenCTM()!)
      // Torso placement follows the yellow trim; the small neckline seam is left unfilled.
      const collar = new DOMPoint(190, 31).matrixTransform(torso.getScreenCTM()!)
      const toRig = (
        document.querySelector('svg[aria-label="Articulated 2D dweller rig"]') as SVGGraphicsElement
      )
        .getScreenCTM()!
        .inverse()
      const localNeck = neck.matrixTransform(toRig)
      const localCollar = collar.matrixTransform(toRig)
      return Math.hypot(localNeck.x - localCollar.x, localNeck.y - localCollar.y)
    })
    expect(gap).toBeLessThan(12)
    bindGap ??= gap
    expect(gap).toBeCloseTo(bindGap, 3)
  }
  await page.getByText('Original art reference: Chet', { exact: true }).click()
  await expect(
    page.getByAltText('Original Fallout Shelter Chet wearing his Vault 33 suit')
  ).toBeVisible()
})

test('keeps the ankle pivots inside the resized shoe artwork', async ({ page }) => {
  await page.goto(path)
  await expect(page.locator('[data-part="frontFoot"] image')).toHaveCount(1)
  const alphas = await page
    .locator('[data-part="frontFoot"] image, [data-part="backFoot"] image')
    .evaluateAll(async (images) =>
      Promise.all(
        images.map(async (image) => {
          const id = image.closest('[data-part]')!.getAttribute('data-part')!
          const circle = document
            .querySelector(`[data-joint="${id}"] circle`)!
            .getBoundingClientRect()
          const ankle = new DOMPoint(
            circle.x + circle.width / 2,
            circle.y + circle.height / 2
          ).matrixTransform((image as SVGGraphicsElement).getScreenCTM()!.inverse())
          const source = new Image()
          source.src = image.getAttribute('href')!
          await source.decode()
          const canvas = document.createElement('canvas')
          canvas.width = source.width
          canvas.height = source.height
          const context = canvas.getContext('2d')!
          context.drawImage(source, 0, 0)
          return context.getImageData(Math.round(ankle.x), Math.round(ankle.y), 1, 1).data[3]!
        })
      )
    )
  for (const alpha of alphas) expect(alpha).toBeGreaterThan(200)
})

test('matches both shoes to Chet’s heel and toe positions, including mirroring', async ({
  page,
}) => {
  await page.goto(path)
  await page.getByRole('button', { name: 'Chet overlay off', exact: true }).click()
  for (const mirrored of [false, true]) {
    if (mirrored) await page.getByRole('button', { name: 'Mirror off', exact: true }).click()
    const gaps = await page.evaluate(() => {
      const reference = document.querySelector(
        '[data-reference="chet"] image'
      ) as SVGGraphicsElement
      const referenceMatrix = reference.getScreenCTM()!
      // Native atlas outline points, compared with the original 136 × 287 portrait.
      const anchors = [
        { id: 'frontFoot', source: [493, 237], target: [70, 283] },
        { id: 'frontFoot', source: [448, 239], target: [110, 274] },
        { id: 'backFoot', source: [426, 237], target: [19, 260] },
        { id: 'backFoot', source: [381, 239], target: [42, 281] },
      ]
      return anchors.map(({ id, source, target }) => {
        const image = document.querySelector(`[data-part="${id}"] image`) as SVGGraphicsElement
        const actual = new DOMPoint(source[0], source[1]).matrixTransform(image.getScreenCTM()!)
        const expected = new DOMPoint(target[0], target[1]).matrixTransform(referenceMatrix)
        return Math.hypot(actual.x - expected.x, actual.y - expected.y)
      })
    })
    for (const gap of gaps) expect(gap).toBeLessThan(1)
  }
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

test('fits each limb alpha contour to its traced region in the original art', async ({ page }) => {
  await page.goto(path)
  await page.getByRole('button', { name: 'Bind pose', exact: true }).click()
  await page.getByRole('button', { name: 'Chet overlay off', exact: true }).click()
  const scores = await page.evaluate(async (outlines) => {
    const reference = document.querySelector('[data-reference]') as SVGGraphicsElement
    const results: Record<string, number> = {}
    for (const [id, polygon] of Object.entries(outlines)) {
      const image = document.querySelector(`[data-part="${id}"] image`) as SVGImageElement
      const source = new Image()
      source.src = image.getAttribute('href')!
      await source.decode()
      const canvas = document.createElement('canvas')
      canvas.width = 136
      canvas.height = 287
      const ctx = canvas.getContext('2d')!
      const matrix = reference.getScreenCTM()!.inverse().multiply(image.getScreenCTM()!)
      ctx.setTransform(matrix)
      const [x, y, w, h] = image.parentElement!.getAttribute('viewBox')!.split(' ').map(Number)
      ctx.drawImage(source, x!, y!, w!, h!, x!, y!, w!, h!)
      const actual = ctx.getImageData(0, 0, 136, 287).data
      ctx.resetTransform()
      ctx.clearRect(0, 0, 136, 287)
      ctx.beginPath()
      polygon.forEach(([x, y], i) => (i ? ctx.lineTo(x!, y!) : ctx.moveTo(x!, y!)))
      ctx.closePath()
      ctx.fill()
      const expected = ctx.getImageData(0, 0, 136, 287).data
      let intersection = 0
      let union = 0
      for (let i = 3; i < actual.length; i += 4) {
        intersection += Math.min(actual[i]!, expected[i]!)
        union += Math.max(actual[i]!, expected[i]!)
      }
      results[id] = intersection / union
    }
    return results
  }, outlines)
  for (const [id, score] of Object.entries(scores))
    expect.soft(score, `${id} contour overlap`).toBeGreaterThan(id === 'backUpperArm' ? 0.64 : 0.72)
})

test('matches yellow trim regions rather than isolated points', async ({ page }) => {
  await page.goto(path)
  await page.getByRole('button', { name: 'Chet overlay off', exact: true }).click()
  const score = await page.evaluate(async () => {
    const reference = document.querySelector('[data-reference] image') as SVGImageElement
    const masks = []
    for (const element of [
      reference,
      document.querySelector('[data-part="spine"] image') as SVGImageElement,
    ]) {
      const source = new Image()
      source.src = element.getAttribute('href')!
      await source.decode()
      const canvas = document.createElement('canvas')
      canvas.width = 136
      canvas.height = 287
      const ctx = canvas.getContext('2d')!
      ctx.setTransform(reference.getScreenCTM()!.inverse().multiply(element.getScreenCTM()!))
      const [x, y, w, h] = element.parentElement!.getAttribute('viewBox')!.split(' ').map(Number)
      ctx.drawImage(source, x!, y!, w!, h!, x!, y!, w!, h!)
      const pixels = ctx.getImageData(0, 0, 136, 287).data
      masks.push(
        Array.from({ length: 136 * 287 }, (_, n) => {
          const i = n * 4
          return (
            pixels[i]! > 110 &&
            pixels[i + 1]! > 95 &&
            pixels[i + 2]! < pixels[i + 1]! * 0.79 &&
            pixels[i]! > pixels[i + 1]! * 0.92 &&
            pixels[i + 3]! > 128
          )
        })
      )
    }
    const scores = [
      [88, 104],
      [104, 153],
      [153, 175],
    ].map(([top, bottom]) => {
      let intersection = 0
      let union = 0
      for (let y = top!; y < bottom!; y++)
        for (let x = 35; x <= 108; x++) {
          const i = y * 136 + x
          intersection += Number(masks[0]![i] && masks[1]![i])
          union += Number(masks[0]![i] || masks[1]![i])
        }
      return intersection / union
    })
    return scores.reduce((sum, value) => sum + value, 0) / 3
  })
  expect(score).toBeGreaterThan(0.6)
})

test('matches open hand silhouettes to the original skin regions', async ({ page }) => {
  await page.goto(path)
  await page.getByRole('button', { name: 'Chet overlay off', exact: true }).click()
  const scores = await page.evaluate(async () => {
    const reference = document.querySelector('[data-reference] image') as SVGImageElement
    const raster = async (element: SVGImageElement) => {
      const source = new Image()
      source.src = element.getAttribute('href')!
      await source.decode()
      const canvas = document.createElement('canvas')
      canvas.width = 136
      canvas.height = 287
      const ctx = canvas.getContext('2d')!
      ctx.setTransform(reference.getScreenCTM()!.inverse().multiply(element.getScreenCTM()!))
      const [x, y, w, h] = element.parentElement!.getAttribute('viewBox')!.split(' ').map(Number)
      ctx.drawImage(source, x!, y!, w!, h!, x!, y!, w!, h!)
      return ctx.getImageData(0, 0, 136, 287).data
    }
    const original = await raster(reference)
    const result: Record<string, number> = {}
    for (const [id, x0, x1, y0, y1] of [
      ['frontHand', 10, 47, 183, 217],
      ['backHand', 111, 136, 174, 208],
    ] as const) {
      const actual = await raster(
        document.querySelector(`[data-part="${id}"] image`) as SVGImageElement
      )
      let intersection = 0
      let union = 0
      for (let y = 0; y < 287; y++)
        for (let x = 0; x < 136; x++) {
          const i = (y * 136 + x) * 4
          const expected =
            x >= x0 &&
            x < x1 &&
            y >= y0 &&
            y < y1 &&
            original[i]! > 95 &&
            original[i + 1]! > 75 &&
            original[i + 2]! < original[i + 1]! * 0.85 &&
            original[i]! > original[i + 1]! * 1.05 &&
            original[i + 3]! > 128
              ? 1
              : 0
          const alpha = actual[i + 3]! / 255
          intersection += Math.min(alpha, expected)
          union += Math.max(alpha, expected)
        }
      result[id] = intersection / union
    }
    return result
  })
  expect.soft(scores.frontHand).toBeGreaterThan(0.5)
  expect.soft(scores.backHand).toBeGreaterThan(0.6)
})

test('edits artwork independently, retains placements across clips and exports them', async ({
  page,
}) => {
  await page.goto(path)
  const upper = page.locator('[data-part="frontUpperArm"] > svg')
  const forearm = page.locator('[data-part="frontForearm"]')
  const forearmBefore = await forearm.getAttribute('transform')
  const xBefore = Number(await upper.getAttribute('x'))
  const width = Number(await upper.getAttribute('width'))
  const height = Number(await upper.getAttribute('height'))
  await expect(page.getByRole('button', { name: 'Flip vertical', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true'
  )
  await page.getByRole('button', { name: 'Move part right', exact: true }).click()
  await expect(upper).toHaveAttribute('x', String(xBefore + 1))
  await expect(forearm).toHaveAttribute('transform', forearmBefore!)
  await page.getByRole('spinbutton', { name: 'Width', exact: true }).fill(String(width * 2))
  await expect(upper).toHaveAttribute('height', String(height * 2))
  await page.getByRole('spinbutton', { name: 'Part rotation', exact: true }).fill('25')
  await expect(upper).toHaveAttribute('transform', /rotate\(25\)/)
  const exported = JSON.parse(
    await page.getByRole('textbox', { name: 'Placement JSON' }).inputValue()
  )
  expect(exported.frontUpperArm.frame[0]).toBe(xBefore + 1)
  expect(exported.frontUpperArm.flipY).toBe(true)
  await page.getByRole('button', { name: 'Walk', exact: true }).click()
  await expect(upper).toHaveAttribute('x', String(xBefore + 1))
  await page.getByRole('button', { name: 'Reset pose', exact: true }).click()
  await expect(upper).toHaveAttribute('x', String(xBefore + 1))
  await page.getByRole('button', { name: 'Reset selected part', exact: true }).click()
  await expect(upper).toHaveAttribute('x', String(xBefore))
  await expect(page.getByRole('textbox', { name: 'Placement JSON' })).toHaveValue('{}')
  await page.getByRole('button', { name: 'Bind pose', exact: true }).click()
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({ path: 'rig-shots/placement-workbench.png', fullPage: true })
})

test('selects, drags, resizes and flips artwork directly in edit mode', async ({ page }) => {
  await page.goto(path)
  await page.getByRole('button', { name: 'Edit mode', exact: true }).click()
  await page
    .locator('section[aria-label="Rig stage"]')
    .screenshot({ path: 'rig-shots/direct-edit.png' })
  const head = page.getByRole('button', { name: 'Edit Head', exact: true })
  const artwork = page.locator('[data-part="head"] > svg')
  const jointBefore = await page.locator('[data-part="head"]').getAttribute('transform')
  const xBefore = Number(await artwork.getAttribute('x'))
  const box = (await head.boundingBox())!
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
  await page.mouse.down()
  await page.mouse.move(box.x + box.width / 2 + 20, box.y + box.height / 2 + 10, { steps: 4 })
  await page.mouse.up()
  await expect(head).toHaveAttribute('aria-pressed', 'true')
  expect(Number(await artwork.getAttribute('x'))).toBeGreaterThan(xBefore)
  await expect(page.locator('[data-part="head"]')).toHaveAttribute('transform', jointBefore!)
  const width = Number(await artwork.getAttribute('width'))
  const ratio = width / Number(await artwork.getAttribute('height'))
  const handle = page.locator('[data-resize-handle="3"]')
  const grip = (await handle.boundingBox())!
  await page.mouse.move(grip.x + grip.width / 2, grip.y + grip.height / 2)
  await page.mouse.down()
  await page.mouse.move(grip.x + grip.width / 2 + 20, grip.y + grip.height / 2 + 20, { steps: 4 })
  await page.mouse.up()
  expect(Number(await artwork.getAttribute('width'))).toBeGreaterThan(width)
  expect(
    Number(await artwork.getAttribute('width')) / Number(await artwork.getAttribute('height'))
  ).toBeCloseTo(ratio)
  await page.getByRole('button', { name: 'Flip selected vertically', exact: true }).click()
  await expect(artwork).toHaveAttribute('transform', /scale\(1 -1\)/)
  await page.getByRole('button', { name: 'Mirror off', exact: true }).click()
  const mirroredBox = (await head.boundingBox())!
  const mirroredX = Number(await artwork.getAttribute('x'))
  await page.mouse.move(
    mirroredBox.x + mirroredBox.width / 2,
    mirroredBox.y + mirroredBox.height / 2
  )
  await page.mouse.down()
  await page.mouse.move(
    mirroredBox.x + mirroredBox.width / 2 + 15,
    mirroredBox.y + mirroredBox.height / 2,
    { steps: 3 }
  )
  await page.mouse.up()
  expect(Number(await artwork.getAttribute('x'))).toBeLessThan(mirroredX)
  await page.getByRole('button', { name: 'Edit mode', exact: true }).click()
  await expect(page.locator('[data-selection-box]')).toHaveCount(0)
})
