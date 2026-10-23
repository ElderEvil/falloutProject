import { mkdir, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { expect, test, type Page, type TestInfo } from '@playwright/test'
import { setAuthToken } from '../e2e/fixtures/auth'
import { createSmallVault, createLargeVault, type VaultFixture } from './vault-fixtures'

const testUser = {
  id: 'test-user-id',
  email: 'overseer@vault-tec.com',
  username: 'overseer',
  is_active: true,
  is_superuser: true,
  email_verified: true,
}

interface InteractionSample {
  name: string
  duration: number
  interactionId: number
}

interface ProbeState {
  interactions: InteractionSample[]
  longFrames: LongFrameSample[]
  startTime: number
  frameIntervals: number[]
  startFrameSampling: () => void
  stopFrameSampling: () => void
  clear: () => void
}

interface LongFrameSample {
  duration: number
  blockingDuration: number
  renderStart: number
  styleAndLayoutStart: number
  scripts: {
    duration: number
    invoker: string
    invokerType: string
    sourceFunctionName: string
    sourceURL: string
    forcedStyleAndLayoutDuration: number
  }[]
}

interface ScenarioReport {
  scenario: string
  elapsedMs?: number | null
  interactionDurationsMs?: number[]
  eventTimingEntries?: number
  longAnimationFramesOver50ms?: LongFrameSample[]
  animationFrameIntervalsMs?: number[]
}

async function installPerformanceProbe(page: Page): Promise<void> {
  await page.addInitScript(() => {
    let frameHandle = 0
    let previousFrame: number | undefined
    const probe: ProbeState = {
      interactions: [],
      longFrames: [],
      startTime: performance.now(),
      frameIntervals: [],
      startFrameSampling() {
        const sample = (timestamp: number) => {
          if (previousFrame !== undefined) this.frameIntervals.push(timestamp - previousFrame)
          previousFrame = timestamp
          frameHandle = requestAnimationFrame(sample)
        }
        frameHandle = requestAnimationFrame(sample)
      },
      stopFrameSampling() {
        cancelAnimationFrame(frameHandle)
      },
      clear() {
        this.stopFrameSampling()
        this.frameIntervals.length = 0
        previousFrame = undefined
        this.interactions.length = 0
        this.longFrames.length = 0
        this.startTime = performance.now()
      },
    }
    Object.defineProperty(window, '__uiPerformanceProbe', { value: probe })

    const supportedTypes = PerformanceObserver.supportedEntryTypes
    if (supportedTypes.includes('event')) {
      new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (entry.startTime < probe.startTime) continue
          const event = entry as PerformanceEntry & { interactionId?: number }
          if (event.interactionId) {
            probe.interactions.push({
              name: event.name,
              duration: event.duration,
              interactionId: event.interactionId,
            })
          }
        }
      }).observe({
        type: 'event',
        durationThreshold: 16,
        buffered: true,
      } as PerformanceObserverInit & { durationThreshold: number })
    }

    if (supportedTypes.includes('long-animation-frame')) {
      new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (entry.startTime < probe.startTime) continue
          const frame = entry as PerformanceEntry & {
            blockingDuration?: number
            renderStart?: number
            styleAndLayoutStart?: number
            scripts?: Array<{
              duration?: number
              invoker?: string
              invokerType?: string
              sourceFunctionName?: string
              sourceURL?: string
              forcedStyleAndLayoutDuration?: number
            }>
          }
          if (frame.duration <= 50) continue
          probe.longFrames.push({
            duration: frame.duration,
            blockingDuration: frame.blockingDuration ?? 0,
            renderStart: frame.renderStart ?? 0,
            styleAndLayoutStart: frame.styleAndLayoutStart ?? 0,
            scripts: (frame.scripts ?? []).map((script) => ({
              duration: script.duration ?? 0,
              invoker: script.invoker ?? '',
              invokerType: script.invokerType ?? '',
              sourceFunctionName: script.sourceFunctionName ?? '',
              sourceURL: script.sourceURL ?? '',
              forcedStyleAndLayoutDuration: script.forcedStyleAndLayoutDuration ?? 0,
            })),
          })
        }
      }).observe({ type: 'long-animation-frame', buffered: true })
    }
  })
}

async function mockOverviewApi(page: Page, fixture: VaultFixture): Promise<void> {
  const { vault, rooms, roster, trainings } = fixture
  await page.route('**/static/dweller_*/**', (route) =>
    route.fulfill({
      path: resolve(
        '../backend/app',
        decodeURIComponent(new URL(route.request().url()).pathname).slice(1)
      ),
    })
  )
  await page.route('**/static/room_images/**', (route) =>
    route.fulfill({
      path: resolve(
        '../backend/app',
        decodeURIComponent(new URL(route.request().url()).pathname).slice(1)
      ),
    })
  )
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname
    const method = route.request().method()

    if (path === '/api/v1/vaults/my') return route.fulfill({ json: [vault] })
    if (path === `/api/v1/vaults/${vault.id}`) return route.fulfill({ json: vault })
    if (path === `/api/v1/rooms/vault/${vault.id}/`) return route.fulfill({ json: rooms })
    if (path === `/api/v1/dwellers/vault/${vault.id}/`) {
      const query = new URL(route.request().url()).searchParams
      const skip = Number(query.get('skip') ?? 0)
      const limit = Number(query.get('limit') ?? 100)
      return route.fulfill({ json: roster.slice(skip, skip + limit) })
    }
    const resident = roster.find((entry) => path === `/api/v1/dwellers/${entry.id}`)
    if (resident) {
      if (method === 'PUT') {
        expect(route.request().postDataJSON()).toEqual({ room_id: null })
        resident.room_id = null
        resident.status = 'idle'
      }
      return route.fulfill({
        json: {
          ...resident,
          vault,
          room: rooms.find((room) => room.id === resident.room_id) ?? null,
          S: resident.strength,
          P: resident.perception,
          E: resident.endurance,
          C: resident.charisma,
          I: resident.intelligence,
          A: resident.agility,
          L: resident.luck,
        },
      })
    }
    const move = path.match(/^\/api\/v1\/dwellers\/([^/]+)\/move_to\/([^/]+)$/)
    if (method === 'POST' && move) {
      const resident = roster.find((entry) => entry.id === move[1])!
      expect(resident).toBeDefined()
      expect(rooms.some((room) => room.id === move[2])).toBe(true)
      resident.room_id = move[2]!
      resident.status = 'working'
      return route.fulfill({ json: resident })
    }
    if (path === `/api/v1/training/vault/${vault.id}`) return route.fulfill({ json: trainings })
    const roomTraining = path.match(/^\/api\/v1\/training\/room\/([^/]+)$/)
    if (roomTraining)
      return route.fulfill({
        json: trainings.filter((record) => record.room_id === roomTraining[1]),
      })
    if (path === `/api/v1/map/vault/${vault.id}`) {
      return route.fulfill({ json: { locations: [] } })
    }
    if (path === `/api/v1/game/vaults/${vault.id}/incidents`) {
      return route.fulfill({ json: { vault_id: vault.id, incident_count: 0, incidents: [] } })
    }
    if (path === '/api/v1/game/balance') {
      return route.fulfill({ json: { resource: { base_production_rate: 0.0012 } } })
    }
    if (path === `/api/v1/storage/vault/${vault.id}/items`) {
      return route.fulfill({ json: { weapons: [], outfits: [], junk: [], items: [], pets: [] } })
    }
    if (path === '/api/v1/system/info') {
      return route.fulfill({ json: { app_version: '2.252.0', environment: 'test' } })
    }
    if (path === '/api/v1/dwellers/identity-options') {
      return route.fulfill({
        json: {
          races: ['human'],
          factions_by_race: { human: [] },
          states_by_race: { human: ['normal'] },
        },
      })
    }
    if (path === `/api/v1/contamination-team/vault/${vault.id}/roster`) {
      return route.fulfill({ json: { vault_id: vault.id, teams: [] } })
    }
    if (method === 'POST' && path === `/api/v1/game/vaults/${vault.id}/presence`) {
      return route.fulfill({ json: { vault_id: vault.id, last_presence_at: null } })
    }
    if (path === '/api/v1/rooms/grid-config/') {
      return route.fulfill({
        json: {
          units_per_room: 3,
          elevator_units: 1,
          floor_units: 28,
          shaft_x: 6,
          left_slot_starts: [0, 3],
          right_slot_starts: [7, 10, 13, 16, 19, 22, 25],
          y_max: 25,
          build_y_max: 15,
        },
      })
    }
    if (path === `/api/v1/game/vaults/${vault.id}/game-state`) {
      return route.fulfill({ json: { is_paused: true, total_game_time: 3600, paused_at: null } })
    }
    if (path === '/api/v1/users/me') return route.fulfill({ json: testUser })
    if (path === '/api/v1/users/me/profile') return route.fulfill({ json: testUser })
    if (path === '/api/v1/system/features') {
      return route.fulfill({ json: { race_mechanics: true, faction_mechanics: true } })
    }
    if (path === '/api/v1/notifications/unread-count') return route.fulfill({ json: { count: 0 } })
    if (path === '/api/v1/notifications/') return route.fulfill({ json: [] })
    if (path.startsWith('/api/v1/stream/')) {
      return route.fulfill({ contentType: 'text/event-stream', body: ': connected\n\n' })
    }
    expect(method, `Unexpected API mutation: ${method} ${path}`).toBe('GET')
    expect(
      [
        `/api/v1/objectives/${vault.id}/`,
        `/api/v1/dwellers/vault/${vault.id}/exit-requests`,
        `/api/v1/explorations/vault/${vault.id}`,
        `/api/v1/training/vault/${vault.id}`,
        `/api/v1/quests/${vault.id}/`,
        `/api/v1/explorations/vault/${vault.id}/pending-overflow`,
      ],
      `Unmocked API request: ${path}`
    ).toContain(path)
    return route.fulfill({ json: [] })
  })
}

async function reportInteraction(
  page: Page,
  testInfo: TestInfo,
  label: string,
  elapsedMs?: number
): Promise<ScenarioReport> {
  await page.evaluate(
    () =>
      new Promise<void>((resolve) => {
        requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(resolve, 0)))
      })
  )

  const sample = await page.evaluate(() => {
    const probe = (window as unknown as { __uiPerformanceProbe: ProbeState }).__uiPerformanceProbe
    probe.stopFrameSampling()
    const grouped = new Map<number, number>()
    for (const event of probe.interactions) {
      grouped.set(
        event.interactionId,
        Math.max(grouped.get(event.interactionId) ?? 0, event.duration)
      )
    }
    return {
      interactionDurationsMs: [...grouped.values()].sort((a, b) => b - a),
      eventTimingEntries: probe.interactions.length,
      longAnimationFramesOver50ms: [...probe.longFrames],
      ...(probe.frameIntervals.length
        ? { animationFrameIntervalsMs: [...probe.frameIntervals] }
        : {}),
    }
  })

  const report = { scenario: label, elapsedMs, ...sample }
  console.log(
    `[ui-performance] ${JSON.stringify({
      scenario: label,
      elapsedMs,
      interactionDurationsMs: sample.interactionDurationsMs,
      longFrameDurationsMs: sample.longAnimationFramesOver50ms.map(({ duration }) => duration),
    })}`
  )
  await testInfo.attach(`${label}-performance.json`, {
    body: JSON.stringify(report, null, 2),
    contentType: 'application/json',
  })
  return report
}

async function measureInteraction(
  page: Page,
  testInfo: TestInfo,
  scenario: string,
  act: () => Promise<unknown>,
  ready: () => Promise<unknown>,
  sampleFrames = false
): Promise<ScenarioReport> {
  const start = await page.evaluate((sampleFrames) => {
    const probe = (window as unknown as { __uiPerformanceProbe: ProbeState }).__uiPerformanceProbe
    probe.clear()
    if (sampleFrames) probe.startFrameSampling()
    return performance.now()
  }, sampleFrames)
  await act()
  await ready()
  const elapsedMs = (await page.evaluate(() => performance.now())) - start
  const report = await reportInteraction(page, testInfo, scenario, elapsedMs)
  expect(
    await page.locator('.toast.border-l-danger').allTextContents(),
    `Visible error toast during ${scenario}`
  ).toEqual([])
  return report
}

test('[small] measures vault overview, management, and navigation', async ({
  page,
  browser,
}, testInfo) => {
  test.setTimeout(60000)
  const fixture = createSmallVault()
  const { vault } = fixture
  const pageErrors: string[] = []
  page.on('pageerror', (error) => pageErrors.push(error.message))
  const reports: ScenarioReport[] = []
  await installPerformanceProbe(page)
  await mockOverviewApi(page, fixture)

  await page.goto('/login')
  await setAuthToken(page, 'deterministic-ui-performance-token', testUser)
  await page.goto(`/vault/${vault.id}`)

  const roomsReady = page.locator('.room.built-room')
  await expect(roomsReady).toHaveCount(2)
  await expect(page.locator('.room-dwellers .dweller-avatar')).toHaveCount(1)
  const overviewReadyMs = await page.evaluate(() => {
    const navigation = performance.getEntriesByType('navigation')[0]
    return navigation ? performance.now() - navigation.startTime : null
  })
  expect(overviewReadyMs).not.toBeNull()
  reports.push(await reportInteraction(page, testInfo, 'vault-overview-ready', overviewReadyMs!))
  const powerRoom = page.getByRole('button', { name: 'Power Generator (Tier 1)', exact: true })
  const waterRoom = page.getByRole('button', { name: 'Water Treatment (Tier 1)', exact: true })
  reports.push(
    await measureInteraction(
      page,
      testInfo,
      'open-room-details',
      () => powerRoom.click(),
      () => expect(page.locator('.room-title')).toHaveText('Power Generator')
    )
  )

  reports.push(
    await measureInteraction(
      page,
      testInfo,
      'open-assignment-picker',
      () => page.getByRole('button', { name: 'Assign worker', exact: true }).click(),
      () =>
        expect(
          page.locator('.dweller-picker').getByRole('button', { name: /Ben Ortiz/ })
        ).toBeVisible()
    )
  )
  reports.push(
    await measureInteraction(
      page,
      testInfo,
      'assign-dweller',
      () =>
        page
          .locator('.dweller-picker')
          .getByRole('button', { name: /Ben Ortiz/ })
          .click(),
      () => expect(page.getByRole('button', { name: 'Open Ben Ortiz', exact: true })).toBeVisible()
    )
  )
  await page.getByRole('button', { name: 'Open Ben Ortiz', exact: true }).hover()
  reports.push(
    await measureInteraction(
      page,
      testInfo,
      'unassign-dweller',
      () => page.getByRole('button', { name: 'Unassign Ben Ortiz', exact: true }).click(),
      () => expect(page.getByRole('button', { name: 'Open Ben Ortiz', exact: true })).toHaveCount(0)
    )
  )

  reports.push(
    await measureInteraction(
      page,
      testInfo,
      'open-dweller-details',
      () => page.getByRole('button', { name: 'Open Ada Wells', exact: true }).click(),
      () =>
        expect(
          page.locator('.dweller-detail').getByRole('heading', { name: 'Ada Wells', exact: true })
        ).toBeVisible()
    )
  )
  await page
    .getByRole('dialog')
    .filter({ has: page.locator('.dweller-detail') })
    .getByRole('button', { name: 'Close', exact: true })
    .click()
  await expect(page.locator('.dweller-detail')).toHaveCount(0)

  await page.getByRole('dialog').getByRole('button', { name: 'Close', exact: true }).click()
  await expect(page.locator('.room-title')).toHaveCount(0)
  reports.push(
    await measureInteraction(
      page,
      testInfo,
      'drag-dweller-between-rooms',
      () => powerRoom.locator('.dweller-avatar').dragTo(waterRoom),
      async () => {
        await expect(waterRoom.locator('.dweller-avatar')).toHaveCount(1)
        await expect(powerRoom.locator('.dweller-avatar')).toHaveCount(0)
      }
    )
  )

  const gameNavigation = page.getByRole('navigation', { name: 'Game navigation panel' })
  for (const section of [
    {
      path: 'dwellers',
      heading: 'Dwellers',
      request: `/api/v1/dwellers/vault/${vault.id}/`,
      ready: () =>
        expect(page.locator('main').getByText('Ada Wells', { exact: true })).toBeVisible(),
    },
    {
      path: 'training',
      heading: 'Training Center',
      request: `/api/v1/training/vault/${vault.id}`,
      ready: () => expect(page.getByRole('heading', { name: /Training Rooms/ })).toBeVisible(),
    },
    {
      path: 'exploration',
      heading: 'Wasteland Exploration',
      request: `/api/v1/quests/${vault.id}/`,
      ready: () => expect(page.getByRole('heading', { name: 'No Active Explorers' })).toBeVisible(),
    },
  ]) {
    reports.push(
      await measureInteraction(
        page,
        testInfo,
        `navigate-to-${section.path}`,
        () =>
          Promise.all([
            page.waitForResponse(
              (response) => new URL(response.url()).pathname === section.request
            ),
            gameNavigation.locator(`a[href="/vault/${vault.id}/${section.path}"]`).click(),
          ]),
        async () => {
          await expect(
            page.getByRole('heading', { name: section.heading, exact: true })
          ).toBeVisible()
          await section.ready()
        }
      )
    )
  }
  reports.push(
    await measureInteraction(
      page,
      testInfo,
      'navigate-to-overview',
      () => gameNavigation.locator(`a[href="/vault/${vault.id}"]`).click(),
      async () => {
        await expect(waterRoom.locator('.dweller-avatar')).toHaveCount(1)
        await expect(powerRoom.locator('.dweller-avatar')).toHaveCount(0)
      }
    )
  )
  expect(pageErrors).toEqual([])

  await saveRun(testInfo, browser.version(), fixture, reports)
})

test('[large] measures grown boosted vault, roster scrolling, and populated training', async ({
  page,
  browser,
}, testInfo) => {
  test.setTimeout(90000)
  const fixture = createLargeVault()
  const { vault, rooms, roster, trainings } = fixture
  const reports: ScenarioReport[] = []
  const pageErrors: string[] = []
  page.on('pageerror', (error) => pageErrors.push(error.message))
  expect(roster).toHaveLength(100)
  expect(trainings).toHaveLength(42)
  for (const room of rooms) {
    expect(room.coordinate_x + room.size).toBeLessThanOrEqual(28)
    expect(
      rooms.filter(
        (other) =>
          other.id !== room.id &&
          other.coordinate_y === room.coordinate_y &&
          other.coordinate_x < room.coordinate_x + room.size &&
          other.coordinate_x + other.size > room.coordinate_x
      )
    ).toHaveLength(0)
    expect(roster.filter((resident) => resident.room_id === room.id).length).toBeLessThanOrEqual(
      Math.ceil(room.size / 3) * 2
    )
  }
  await installPerformanceProbe(page)
  await mockOverviewApi(page, fixture)
  await page.goto('/login')
  await setAuthToken(page, 'deterministic-ui-performance-token', testUser)
  await page.goto(`/vault/${vault.id}`)
  await expect(page.locator('.room.built-room')).toHaveCount(rooms.length)
  await expect(page.locator('.room-dwellers .dweller-avatar')).toHaveCount(roster.length)
  reports.push(
    await reportInteraction(
      page,
      testInfo,
      'vault-overview-ready',
      await page.evaluate(() => performance.now())
    )
  )

  const powerRoom = rooms.find((room) => room.name === 'Power Generator')!
  const tile = page
    .getByRole('button', { name: `${powerRoom.name} (Tier ${powerRoom.tier})`, exact: true })
    .first()
  await tile.scrollIntoViewIfNeeded()
  reports.push(
    await measureInteraction(
      page,
      testInfo,
      'open-room-details',
      () => tile.click(),
      async () => {
        await expect(page.locator('.room-title')).toHaveText(powerRoom.name)
        for (const resident of roster.filter((resident) => resident.room_id === powerRoom.id)) {
          await expect(
            page.getByRole('button', {
              name: `Open ${resident.first_name} ${resident.last_name}`,
              exact: true,
            })
          ).toBeVisible()
        }
      }
    )
  )
  await page.getByRole('dialog').getByRole('button', { name: 'Close', exact: true }).click()
  await expect(page.locator('.room-title')).toHaveCount(0)
  const nav = page.getByRole('navigation', { name: 'Game navigation panel' })
  const rows = page.locator('main .dweller-list-row')
  reports.push(
    await measureInteraction(
      page,
      testInfo,
      'navigate-to-dwellers',
      () => nav.locator(`a[href="/vault/${vault.id}/dwellers"]`).click(),
      () => expect(rows).toHaveCount(roster.length)
    )
  )
  await rows.first().scrollIntoViewIfNeeded()
  await page.mouse.move(1000, 600)
  const scrollStart = await page.evaluate(() => window.scrollY)
  const scrollReport = await measureInteraction(
    page,
    testInfo,
    'scroll-dweller-roster',
    async () => {
      // A paced wheel gesture exercises scrolling over many rendered rows.
      for (let step = 0; step < 14; step++) {
        await page.mouse.wheel(0, 1000)
        await page.waitForTimeout(80)
      }
    },
    async () => {
      await expect(rows.last()).toBeInViewport()
      expect(await page.evaluate(() => window.scrollY)).toBeGreaterThan(scrollStart + 500)
    },
    true
  )
  expect(scrollReport.animationFrameIntervalsMs?.length ?? 0).toBeGreaterThan(10)
  reports.push(scrollReport)
  const lastResident = roster.at(-1)!
  reports.push(
    await measureInteraction(
      page,
      testInfo,
      'open-last-dweller-details',
      () => rows.last().click(),
      () =>
        expect(
          page.locator('.dweller-detail').getByRole('heading', {
            name: `${lastResident.first_name} ${lastResident.last_name}`,
            exact: true,
          })
        ).toBeVisible()
    )
  )
  await page.getByRole('button', { name: 'Back', exact: true }).click()
  await expect(page.locator('.dweller-detail')).toHaveCount(0)
  const queue = page.locator('.training-queue-panel')
  reports.push(
    await measureInteraction(
      page,
      testInfo,
      'navigate-to-training',
      () => nav.locator(`a[href="/vault/${vault.id}/training"]`).click(),
      async () => {
        await expect(
          page.getByRole('heading', { name: 'Training Center', exact: true })
        ).toBeVisible()
        await expect(queue.locator('.training-progress-card')).toHaveCount(trainings.length)
        await expect(queue.locator('details')).toHaveCount(7)
        await expect(queue.getByText('Resident 001 Vale', { exact: true })).toHaveCount(1)
      }
    )
  )
  const strengthGroup = queue
    .locator('details')
    .filter({ has: page.locator('summary').filter({ hasText: 'Strength' }) })
  await strengthGroup.locator('summary').scrollIntoViewIfNeeded()
  reports.push(
    await measureInteraction(
      page,
      testInfo,
      'collapse-training-type',
      () => strengthGroup.locator('summary').click(),
      () => expect(strengthGroup.locator('.training-progress-card').first()).not.toBeVisible()
    )
  )
  reports.push(
    await measureInteraction(
      page,
      testInfo,
      'expand-training-type',
      () => strengthGroup.locator('summary').click(),
      () => expect(strengthGroup.locator('.training-progress-card').first()).toBeVisible()
    )
  )
  const trainingRoom = rooms.find((room) => room.category === 'training')!
  const trainingLink = page
    .getByRole('link', { name: `Open ${trainingRoom.name}`, exact: true })
    .first()
  await trainingLink.scrollIntoViewIfNeeded()
  reports.push(
    await measureInteraction(
      page,
      testInfo,
      'open-populated-training-room',
      () => trainingLink.click(),
      async () => {
        await expect(page.locator('.room-title')).toHaveText(trainingRoom.name)
        const progress = page.getByRole('region', { name: 'Training progress' })
        await expect(progress.locator('.training-progress-card')).toHaveCount(2)
        await expect(
          progress.getByRole('heading', { name: 'Training (2/2)', exact: true })
        ).toBeVisible()
      }
    )
  )
  expect(pageErrors).toEqual([])
  await saveRun(testInfo, browser.version(), fixture, reports)
})

async function saveRun(
  testInfo: TestInfo,
  browserVersion: string,
  fixture: VaultFixture,
  reports: ScenarioReport[]
): Promise<void> {
  const resultsDirectory = process.env.UI_PERF_RESULTS_DIR
  if (!resultsDirectory)
    throw new Error('UI_PERF_RESULTS_DIR must be set by the performance runner')
  const runNumber = String(testInfo.repeatEachIndex + 1).padStart(2, '0')
  const reportPath = resolve(resultsDirectory, `${fixture.name}-run-${runNumber}.json`)
  await mkdir(dirname(reportPath), { recursive: true })
  await writeFile(
    reportPath,
    JSON.stringify(
      {
        run: testInfo.repeatEachIndex + 1,
        recordedAt: new Date().toISOString(),
        browser: 'chromium',
        browserVersion,
        viewport: '1280x900',
        measurementVersion: 4,
        tracing: process.env.UI_PERF_TRACE === '1',
        workload: fixture.name,
        fixture: {
          roomLayout: fixture.name === 'large' ? 'grown-boosted-v1' : 'two-room-v1',
          rooms: fixture.rooms.length,
          dwellers: fixture.roster.length,
          activeTrainings: fixture.trainings.length,
          trainingRooms: fixture.rooms.filter((room) => room.category === 'training').length,
        },
        scenarios: reports,
      },
      null,
      2
    )
  )
  await testInfo.attach('ui-performance-run.json', {
    path: reportPath,
    contentType: 'application/json',
  })
}
