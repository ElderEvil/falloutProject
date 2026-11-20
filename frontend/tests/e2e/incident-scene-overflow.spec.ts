import { test, expect } from '@playwright/test'

// Owner report: "during incident combat scrollbar appears next to dwellers in
// some rooms with some opponents". The responder lane must absorb any roster
// (residents + up to six helpers) without ever becoming a scroll container,
// regardless of viewport, roster size, opponent type or name length.
test.beforeEach(async ({ page }) => {
  await page.route('**/static/**', (route) =>
    route.fulfill({
      contentType: 'image/svg+xml',
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect width="100" height="100" fill="green"/></svg>',
    })
  )
})

interface OverflowReport {
  scene: { scrollWidth: number; clientWidth: number; scrollHeight: number; clientHeight: number }
  row: { scrollWidth: number; clientWidth: number; scrollHeight: number; clientHeight: number }
  scrollable: { selector: string; axis: string; scroll: number; client: number }[]
  clipped: number[]
}

async function measure(page: import('@playwright/test').Page): Promise<OverflowReport> {
  return page.evaluate(() => {
    const scene = document.querySelector('.incident-scene') as HTMLElement
    const row = scene.querySelector('.incident-responder')?.parentElement as HTMLElement
    const box = (el: HTMLElement) => ({
      scrollWidth: el.scrollWidth,
      clientWidth: el.clientWidth,
      scrollHeight: el.scrollHeight,
      clientHeight: el.clientHeight,
    })
    // Any element that opts into scrolling (overflow auto/scroll) must not
    // actually have overflowing content — that is the scrollbar the owner sees.
    const scrollable: OverflowReport['scrollable'] = []
    scene.querySelectorAll<HTMLElement>('*').forEach((el, index) => {
      const style = getComputedStyle(el)
      const selector = `${el.tagName.toLowerCase()}${el.className ? `.${String(el.className).split(' ')[0]}` : ''}[${index}]`
      for (const axis of ['x', 'y'] as const) {
        const overflow = style.getPropertyValue(`overflow-${axis}`)
        if (overflow !== 'auto' && overflow !== 'scroll') continue
        const scroll = axis === 'x' ? el.scrollWidth : el.scrollHeight
        const client = axis === 'x' ? el.clientWidth : el.clientHeight
        if (scroll > client + 1) scrollable.push({ selector, axis, scroll, client })
      }
    })
    // Every responder must sit fully inside the scene — no clipping, no hiding.
    const sceneBox = scene.getBoundingClientRect()
    const clipped: number[] = []
    scene.querySelectorAll<HTMLElement>('.incident-responder').forEach((el, index) => {
      const rect = el.getBoundingClientRect()
      if (rect.left < sceneBox.left - 1 || rect.right > sceneBox.right + 1) clipped.push(index)
    })
    return { scene: box(scene), row: box(row), scrollable, clipped }
  })
}

function expectNoOverflow(report: OverflowReport) {
  expect(report.scrollable, 'no scrollable overflow inside the scene').toEqual([])
  expect(report.clipped, 'no responder clipped by the scene edge').toEqual([])
  expect(report.row.scrollWidth, 'responder row horizontal overflow').toBeLessThanOrEqual(
    report.row.clientWidth
  )
  expect(report.row.scrollHeight, 'responder row vertical overflow').toBeLessThanOrEqual(
    report.row.clientHeight
  )
  expect(report.scene.scrollWidth, 'scene horizontal overflow').toBeLessThanOrEqual(
    report.scene.clientWidth
  )
  expect(report.scene.scrollHeight, 'scene vertical overflow').toBeLessThanOrEqual(
    report.scene.clientHeight
  )
}

for (const width of [390, 1280]) {
  for (const count of [2, 4, 5, 6, 8, 12]) {
    for (const longNames of [false, true]) {
      const label = longNames ? 'long names' : 'short names'
      test(`${count} responders (${label}) never scroll the scene at ${width}px`, async ({
        page,
      }) => {
        await page.setViewportSize({ width, height: 900 })
        await page.goto(
          `/tests/e2e/fixtures/incident-scene.html?responders=${count}${longNames ? '&longNames' : ''}`
        )
        const scene = page.getByRole('region', { name: 'Incident live status' })
        await expect(scene.locator('.incident-responder')).toHaveCount(count)
        expectNoOverflow(await measure(page))
        await expect(scene.locator('.incident-responder').last()).toBeInViewport()
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
          true
        )
      })
    }
  }
}

// "Some opponents": sweep creature types at a roster size that already stresses
// the lane, with long names, at both viewports.
for (const width of [390, 1280]) {
  for (const type of ['raider_attack', 'radroach_infestation', 'mole_rat_attack']) {
    test(`${type} with 6 long-named responders never scrolls at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 })
      await page.goto(`/tests/e2e/fixtures/incident-scene.html?type=${type}&responders=6&longNames`)
      const scene = page.getByRole('region', { name: 'Incident live status' })
      await expect(scene.locator('.incident-responder')).toHaveCount(6)
      expectNoOverflow(await measure(page))
    })
  }
}
