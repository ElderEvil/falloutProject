import { test, expect, type Page } from '@playwright/test'

/**
 * First-frame layout probe for the room preview.
 *
 * `#1187` flashed oversized portraits and silhouettes for several frames in
 * Firefox because the slot chain sized itself from container-query units while
 * the frame was still resolving. The preview now reserves the frame first and
 * sizes slots from a percentage band. This probe samples every animation frame
 * from page start, so a regression that only shows on the first painted frames
 * fails instead of passing on the settled layout.
 *
 * The frame/slot contract: the room image frame owns width, height and
 * `--portrait-frame-aspect`; a slot is 100% of the 44.6% occupant band and the
 * occupant is the 2:3 portrait frame. See `docs/frontend/STYLEGUIDE.md`.
 */

interface FrameSample {
  mount: number
  frameW: number
  frameH: number
  slotW: number
  slotH: number
  occupantW: number
  occupantH: number
}

const ROOM_IMAGE = '/e2e-room-image.svg'
const BROKEN_IMAGE = '/e2e-broken-image.png'
const ROOM_SVG =
  '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="400">' +
  '<rect width="1200" height="400" fill="#102a10"/><circle cx="300" cy="300" r="60" fill="#1f5f1f"/>' +
  '</svg>'
const PREVIEW = '/tests/e2e/fixtures/room-preview.html'

async function installProbe(page: Page): Promise<void> {
  await page.addInitScript(() => {
    interface Sample {
      mount: number
      frameW: number
      frameH: number
      slotW: number
      slotH: number
      occupantW: number
      occupantH: number
    }
    const samples: Sample[] = []
    const target = window as unknown as {
      __sizingSamples?: Sample[]
      __sizingSamplesReset?: () => void
    }
    target.__sizingSamples = samples
    target.__sizingSamplesReset = () => {
      samples.length = 0
    }
    const started = performance.now()
    const tick = () => {
      const host = document.querySelector<HTMLElement>('[data-preview-mount]')
      const frame = document.querySelector<HTMLElement>('.room-image-frame')
      const slot = document.querySelector<HTMLElement>('.dweller-sprite-slot')
      const occupant = document.querySelector<HTMLElement>('.scene-occupant')
      if (host && frame && slot && occupant) {
        const f = frame.getBoundingClientRect()
        const s = slot.getBoundingClientRect()
        const o = occupant.getBoundingClientRect()
        // The overlay is intentionally absent until the image aspect is known;
        // once a slot exists, every painted frame must agree with the settled
        // geometry.
        if (f.width > 0 && f.height > 0) {
          samples.push({
            mount: Number(host.dataset.previewMount ?? 0),
            frameW: f.width,
            frameH: f.height,
            slotW: s.width,
            slotH: s.height,
            occupantW: o.width,
            occupantH: o.height,
          })
        }
      }
      if (performance.now() - started < 8000 && samples.length < 900) requestAnimationFrame(tick)
    }
    requestAnimationFrame(tick)
  })
}

async function serveRoomImage(page: Page, delayMs = 0): Promise<void> {
  await page.route(`**${ROOM_IMAGE}`, async (route) => {
    if (delayMs > 0) await new Promise((resolve) => setTimeout(resolve, delayMs))
    await route.fulfill({
      status: 200,
      contentType: 'image/svg+xml',
      headers: { 'Cache-Control': 'public, max-age=3600' },
      body: ROOM_SVG,
    })
  })
}

async function readSamples(page: Page): Promise<FrameSample[]> {
  return page.evaluate(
    () =>
      (window as unknown as { __sizingSamples?: FrameSample[] }).__sizingSamples ??
      ([] as FrameSample[])
  )
}

async function resetSamples(page: Page): Promise<void> {
  await page.evaluate(() =>
    (window as unknown as { __sizingSamplesReset?: () => void }).__sizingSamplesReset?.()
  )
}

/** Wait for at least three painted frames of this preview mount. */
async function samplesForMount(page: Page, mount: number): Promise<FrameSample[]> {
  await expect
    .poll(async () => (await readSamples(page)).filter((sample) => sample.mount === mount).length, {
      timeout: 10_000,
    })
    .toBeGreaterThan(2)
  return (await readSamples(page)).filter((sample) => sample.mount === mount)
}

/**
 * Assert the painted frames never disagree with the settled geometry.
 * `expectedFrameRatio` pins the settled aspect when the test knows it.
 */
function expectStableFrame(samples: FrameSample[], expectedFrameRatio?: number): void {
  expect(samples.length).toBeGreaterThan(2)

  // The occupant band is 44.6% of the frame; a first frame that paints three
  // times too large lands far outside this window.
  const occupantRatios = samples.map((sample) => sample.occupantH / sample.frameH)
  expect(Math.min(...occupantRatios)).toBeGreaterThan(0.3)
  expect(Math.max(...occupantRatios)).toBeLessThan(0.55)
  expect(Math.max(...occupantRatios) - Math.min(...occupantRatios)).toBeLessThanOrEqual(0.02)

  for (const sample of samples) {
    expect(sample.slotW / sample.slotH).toBeCloseTo(2 / 3, 1)
    expect(sample.occupantW / sample.occupantH).toBeCloseTo(2 / 3, 1)
    expect(sample.occupantH).toBeLessThanOrEqual(sample.slotH + 1)
  }

  // The frame itself must not resize after the overlay appears.
  const frameRatios = samples.map((sample) => sample.frameW / sample.frameH)
  expect(Math.max(...frameRatios) - Math.min(...frameRatios)).toBeLessThanOrEqual(0.05)
  if (expectedFrameRatio !== undefined) {
    for (const ratio of frameRatios) expect(ratio).toBeCloseTo(expectedFrameRatio, 1)
  }
}

test('first painted frame stays actor-sized while the room image loads', async ({ page }) => {
  await installProbe(page)
  await serveRoomImage(page, 400)
  await page.goto(`${PREVIEW}?room=${encodeURIComponent(ROOM_IMAGE)}&portrait=1`, {
    waitUntil: 'domcontentloaded',
  })
  await expect(page.locator('.dweller-sprites-overlay')).toBeVisible()

  const samples = await samplesForMount(page, 1)
  expectStableFrame(samples)

  // The settled frame is the loaded 1200x400 image, not the pre-load placeholder.
  expect(samples.at(-1)!.frameW / samples.at(-1)!.frameH).toBeCloseTo(3, 0)
})

test('revealing a mounted preview keeps the first visible frame stable', async ({ page }) => {
  await installProbe(page)
  await serveRoomImage(page, 150)
  await page.goto(`${PREVIEW}?room=${encodeURIComponent(ROOM_IMAGE)}&portrait=1&reveal=1`, {
    waitUntil: 'domcontentloaded',
  })
  await expect(page.locator('.dweller-sprites-overlay')).toBeVisible()

  // The preview mounts at zero height and is revealed 80ms later, so these are
  // the first frames a modal-opening layout change paints.
  expectStableFrame(await samplesForMount(page, 1), 3)
})

test('cached reopen paints the measured aspect on its first frame', async ({ page }) => {
  await installProbe(page)
  await serveRoomImage(page)
  await page.goto(`${PREVIEW}?room=${encodeURIComponent(ROOM_IMAGE)}&portrait=1&reopen=1`, {
    waitUntil: 'domcontentloaded',
  })
  await expect(page.locator('.dweller-sprites-overlay')).toBeVisible()

  const initial = await samplesForMount(page, 1)
  expectStableFrame(initial, 3)
  const settledRatio = initial.at(-1)!.frameW / initial.at(-1)!.frameH

  await resetSamples(page)
  await page.locator('#reopen-preview').click()

  // Mount 2 is the remount. Its first painted frame is what regressed in #1187.
  const reopened = await samplesForMount(page, 2)
  expectStableFrame(reopened, settledRatio)
  expect(reopened[0]!.frameW / reopened[0]!.frameH).toBeCloseTo(settledRatio, 1)
})

test('failed room image keeps the reserved frame and slot geometry', async ({ page }) => {
  await installProbe(page)
  await page.route(`**${BROKEN_IMAGE}`, (route) => route.fulfill({ status: 404, body: '' }))
  await page.goto(`${PREVIEW}?room=${encodeURIComponent(BROKEN_IMAGE)}&portrait=1`, {
    waitUntil: 'domcontentloaded',
  })
  await expect(page.locator('.dweller-sprites-overlay')).toBeVisible()

  expectStableFrame(await samplesForMount(page, 1))
})

test('empty slots share the same frame contract', async ({ page }) => {
  await installProbe(page)
  await serveRoomImage(page)
  await page.goto(`${PREVIEW}?room=${encodeURIComponent(ROOM_IMAGE)}&empty=1&portrait=1`, {
    waitUntil: 'domcontentloaded',
  })
  await expect(page.locator('.dweller-sprites-overlay')).toBeVisible()
  await expect(page.locator('.empty-dweller-silhouette').first()).toBeVisible()

  expectStableFrame(await samplesForMount(page, 1), 3)
})

test.describe('narrow viewport', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  test('first frame is stable at phone width', async ({ page }) => {
    await installProbe(page)
    await serveRoomImage(page, 300)
    await page.goto(`${PREVIEW}?room=${encodeURIComponent(ROOM_IMAGE)}&portrait=1`, {
      waitUntil: 'domcontentloaded',
    })
    await expect(page.locator('.dweller-sprites-overlay')).toBeVisible()

    expectStableFrame(await samplesForMount(page, 1))
  })
})

test('full pet rooms keep stable actor sizes from the first painted frame', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await installProbe(page)
  await serveRoomImage(page, 150)
  await page.goto(
    `${PREVIEW}?room=${encodeURIComponent(ROOM_IMAGE)}&pet=1&full=1&portrait=1&reveal=1&reopen=1`
  )
  await expect(page.locator('.combat-pet')).toHaveCount(6)
  expectStableFrame(await samplesForMount(page, 1), 3)
  await resetSamples(page)
  await page.getByRole('button', { name: 'Reopen preview' }).click()
  expectStableFrame(await samplesForMount(page, 2), 3)
})
