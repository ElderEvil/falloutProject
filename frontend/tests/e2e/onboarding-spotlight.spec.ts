import { test, expect, type Page } from '@playwright/test'
import { setAuthToken, type TestUser } from './fixtures/auth'

// Browser coverage for the spotlight guide (#1001): the card and cut-out must
// coexist with the real vault UI at phone width, and the guide must yield to a
// dialog without losing the pending lesson. All backend traffic is mocked, so
// the assertions depend only on frontend markup and state.
test.use({
  locale: 'en-US',
  timezoneId: 'UTC',
  viewport: { width: 1280, height: 900 },
  // Reduced motion removes the side-panel slide, so resize/hide timing is
  // deterministic instead of racing a 300ms transition.
  reducedMotion: 'reduce',
})

const TOKEN = 'deterministic-e2e-token'

const AUTH_USER: TestUser = {
  id: 'test-user-id',
  username: 'overseer',
  email: 'overseer@vault-tec.com',
  is_active: true,
  is_superuser: true,
  email_verified: true,
}

const VAULT = {
  id: 'vault-1',
  number: 42,
  bottle_caps: 1250,
  happiness: 82,
  power: 80,
  power_max: 100,
  food: 70,
  food_max: 100,
  water: 18,
  water_max: 100,
  population_max: 10,
  radio_mode: 'happiness',
  created_at: '2026-01-15T10:30:00Z',
  updated_at: '2026-01-15T10:30:00Z',
  resource_warnings: [],
  room_count: 1,
  dweller_count: 8,
  stimpack: 4,
  radaway: 2,
}

// The staffing lesson only highlights when its objective is present and eligible.
const STAFFING_OBJECTIVE = {
  id: 'obj-staffing',
  challenge: 'Match a dweller to their room',
  description: 'Do the thing.',
  progress: 0,
  total: 2,
  reward: '25 caps',
  is_completed: false,
  category: 'starter',
  sequence: 1,
  template_key: 'starter:assign a dweller correctly#v2',
  objective_type: 'assign_correct',
  target_entity: {},
  created_at: '2026-01-15T10:30:00Z',
}

const ORIENTATION_ACKNOWLEDGED = {
  version: 1,
  lessons: {
    'orientation.resources': 'acknowledged',
    'orientation.generator': 'acknowledged',
    'orientation.food': 'acknowledged',
    'orientation.diner': 'acknowledged',
    'orientation.water': 'acknowledged',
    'orientation.water-treatment': 'acknowledged',
  },
  replayOrientation: false,
}

// Only the first lesson needs acknowledging to reach the generator lesson, whose
// `room-power` anchor sits in the scrollable room grid (unlike the fixed chrome).
const RESOURCES_ACKNOWLEDGED = {
  version: 1,
  lessons: { 'orientation.resources': 'acknowledged' },
  replayOrientation: false,
}

const POWER_ROOM = {
  id: 'room-1',
  vault_id: 'vault-1',
  name: 'Power Plant',
  category: 'Production',
  ability: 'strength',
  level: 1,
  max_level: 3,
  row: 0,
  col: 0,
  width: 1,
  height: 1,
  is_max_level: false,
  assigned_dwellers: [],
  production_rate: null,
  resource_type: 'power',
  build_cost: 0,
  upgrade_cost: 0,
  created_at: '2026-01-15T10:30:00Z',
  updated_at: '2026-01-15T10:30:00Z',
}

async function mockApi(page: Page) {
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname

    if (path === '/api/v1/users/me') return route.fulfill({ json: AUTH_USER })
    if (path === '/api/v1/game/balance') {
      return route.fulfill({ json: { resource: { base_production_rate: 1 } } })
    }
    if (path === '/api/v1/game/vaults/vault-1/incidents') {
      return route.fulfill({ json: { incidents: [] } })
    }
    if (path === '/api/v1/vaults/my') return route.fulfill({ json: [VAULT] })
    if (path === '/api/v1/vaults/vault-1') return route.fulfill({ json: VAULT })
    if (path === '/api/v1/objectives/vault-1/') {
      return route.fulfill({ json: [STAFFING_OBJECTIVE] })
    }
    if (path === '/api/v1/rooms/vault/vault-1/') {
      return route.fulfill({ json: [POWER_ROOM] })
    }
    if (path === '/api/v1/notifications/unread-count') return route.fulfill({ json: { count: 0 } })
    if (path === '/api/v1/notifications/') return route.fulfill({ json: [] })
    if (path.startsWith('/api/v1/stream/')) {
      return route.fulfill({ contentType: 'text/event-stream', body: ': connected\n\n' })
    }
    // Everything else the vault shell polls is benign when empty.
    return route.fulfill({ json: [] })
  })
}

async function openVault(page: Page, teaching?: unknown) {
  await page.addInitScript(
    (record) => {
      // Opt this vault into the orientation and seed the "What's New" key so the
      // changelog modal never races the guide.
      // Seed once: a reload must preserve progress and handoff dismissal.
      if (!window.localStorage.getItem('onboarding:v1')) {
        window.localStorage.setItem('onboarding:v1', JSON.stringify(record))
      }
      window.localStorage.setItem('fallout_changelog_last_seen', '999.0.0')
    },
    { 'vault-1': { created: true, ...(teaching ? { welcomed: true, teaching } : {}) } }
  )
  await mockApi(page)
  await page.goto('/login')
  await setAuthToken(page, TOKEN, AUTH_USER)
  await page.goto('/vault/vault-1')
}

test.describe('Spotlight guide — vault page', () => {
  test('shows the guide and highlights an on-screen control at phone width', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await openVault(page)

    await expect(page.getByText('Welcome, Overseer')).toBeVisible({ timeout: 15000 })
    await page.getByRole('button', { name: 'Start' }).click()

    const card = page.locator('.onboarding-card')
    await expect(card).toBeVisible()
    await expect(card).toContainText('Keep the power on')

    // The guide must not cover the control it points at.
    const cutout = page.locator('.onboarding-cutout')
    await expect(cutout).toBeAttached({ timeout: 10000 })
    const cutoutBox = await cutout.boundingBox()
    const cardBox = await card.boundingBox()
    expect(cutoutBox).not.toBeNull()
    expect(cardBox).not.toBeNull()
    const overlaps =
      cutoutBox!.x < cardBox!.x + cardBox!.width &&
      cutoutBox!.x + cutoutBox!.width > cardBox!.x &&
      cutoutBox!.y < cardBox!.y + cardBox!.height &&
      cutoutBox!.y + cutoutBox!.height > cardBox!.y
    expect(overlaps).toBe(false)
  })

  test('teaches power, food and water with their rooms one by one', async ({ page }) => {
    await openVault(page)
    const rooms = [
      { id: 'power', name: 'Power generator', ability: 'strength', coordinate_x: 0 },
      { id: 'food', name: 'Diner', ability: 'agility', coordinate_x: 3 },
      { id: 'water', name: 'Water treatment', ability: 'perception', coordinate_x: 7 },
    ].map((room) => ({
      ...POWER_ROOM,
      category: 'Production',
      size: 3,
      tier: 1,
      coordinate_y: 0,
      ...room,
    }))
    await page.route('**/api/v1/rooms/vault/vault-1/', (route) => route.fulfill({ json: rooms }))
    await page.reload()
    await page.getByRole('button', { name: 'Start' }).click()
    const card = page.getByRole('region', { name: 'Vault onboarding' })
    for (const [anchor, title] of [
      ['resource-power', 'Keep the power on'],
      ['room-power', 'Open the Power Generator'],
      ['resource-food', 'Keep your dwellers fed'],
      ['room-food', 'Open the Diner'],
      ['resource-water', 'Keep clean water flowing'],
      ['room-water', 'Open Water Treatment'],
    ]) {
      await expect(card.getByRole('heading', { name: title, exact: true })).toBeVisible()
      await expect(page.locator('.onboarding-cutout')).toHaveCount(1)
      await expect
        .poll(() =>
          page.evaluate((key) => {
            const target = document
              .querySelector(`[data-onboarding="${key}"]`)
              ?.getBoundingClientRect()
            const highlight = document.querySelector('.onboarding-cutout')?.getBoundingClientRect()
            return target && highlight
              ? Math.max(Math.abs(highlight.x - target.x + 4), Math.abs(highlight.y - target.y + 4))
              : Infinity
          }, anchor)
        )
        .toBeLessThan(2)
      // Bounds and the default collapsed state settle on the next animation frame.
      await page.evaluate(
        () =>
          new Promise<void>((resolve) =>
            requestAnimationFrame(() => requestAnimationFrame(() => resolve()))
          )
      )
      const expand = card.getByRole('button', { name: 'Expand guide' })
      if (await expand.isVisible()) await expand.click()
      await card.getByRole('button', { name: 'Continue', exact: true }).click()
    }
    await expect(card.getByRole('heading', { name: 'Understand SPECIAL staffing' })).toBeVisible()
  })

  test('yields the guide to a dialog and resumes the same lesson', async ({ page }) => {
    await openVault(page)
    await expect(page.getByText('Welcome, Overseer')).toBeVisible({ timeout: 15000 })
    await page.getByRole('button', { name: 'Start' }).click()

    const card = page.locator('.onboarding-card')
    await expect(card).toBeVisible()

    // The notification panel is a dialog-role overlay; the guide must give way.
    await page.getByRole('button', { name: 'Notifications' }).click()
    await expect(page.getByRole('dialog', { name: 'Notifications' })).toBeVisible()
    await expect(card).toHaveCount(0)

    await page.keyboard.press('Escape')
    await expect(page.getByRole('dialog', { name: 'Notifications' })).toHaveCount(0)
    await expect(card).toBeVisible()
    await expect(card).toContainText('Keep the power on')
  })

  test('keyboard-activates the highlighted control when it is on screen', async ({ page }) => {
    await openVault(page, ORIENTATION_ACKNOWLEDGED)

    const control = page.locator('[data-onboarding="nav-dwellers"]')
    await expect(control).toBeVisible({ timeout: 15000 })

    await control.focus()
    await expect(control).toBeFocused()
    await page.keyboard.press('Enter')

    await expect(page).toHaveURL(/\/vault\/vault-1\/dwellers/, { timeout: 10000 })
  })

  test('offers explicit navigation at phone width when the control is hidden', async ({ page }) => {
    // The side panel collapses below the desktop breakpoint, so the staffing
    // anchor is hidden; the guide must navigate rather than spotlight nothing.
    await page.setViewportSize({ width: 390, height: 844 })
    await openVault(page, ORIENTATION_ACKNOWLEDGED)

    await expect(page.getByRole('button', { name: 'Open Dwellers' })).toBeVisible({
      timeout: 15000,
    })
    await expect(page.locator('.onboarding-cutout--off')).toHaveCount(0)
  })

  test('re-resolves the guide when resizing hides the control', async ({ page }) => {
    await openVault(page, ORIENTATION_ACKNOWLEDGED)
    await expect(page.locator('.onboarding-cutout')).toBeAttached({ timeout: 15000 })

    // Below the desktop breakpoint the side panel collapses, hiding the anchor;
    // the detached spotlight must go and a fallback action must appear (navigate
    // when the control is gone, scroll when it is merely out of view).
    await page.setViewportSize({ width: 390, height: 844 })

    await expect(page.locator('.onboarding-cutout')).toHaveCount(0)
    await expect(
      page.locator('.onboarding-actions button', { hasText: /Open Dwellers|Show control/ })
    ).toBeVisible({ timeout: 10000 })
  })

  test('restores the spotlight after Show control scrolls the control into view', async ({
    page,
  }) => {
    // A short viewport leaves the power room below the fold while it is present
    // in the DOM, which is exactly the off-screen case the scroll path serves.
    await page.setViewportSize({ width: 1280, height: 360 })
    await openVault(page, RESOURCES_ACKNOWLEDGED)

    const showControl = page.getByRole('button', { name: 'Show control' })
    await expect(showControl).toBeVisible({ timeout: 15000 })
    await expect(page.locator('.onboarding-cutout')).toHaveCount(0)

    await showControl.click()

    await expect(page.locator('.onboarding-cutout')).toBeAttached({ timeout: 10000 })
    await expect(page.getByRole('button', { name: 'Show control' })).toHaveCount(0)
  })

  for (const viewport of [
    { width: 1280, height: 900 },
    { width: 390, height: 844 },
  ]) {
    test(`housing highlights the room, supports search and guides placement at ${viewport.width}px`, async ({
      page,
    }) => {
      await page.setViewportSize(viewport)
      await openVault(page, {
        ...ORIENTATION_ACKNOWLEDGED,
        lessons: {
          ...ORIENTATION_ACKNOWLEDGED.lessons,
          'orientation.staffing': 'acknowledged',
        },
      })
      let built = false
      let builtRooms: Record<string, unknown>[] = []
      const living = {
        name: 'Living room',
        category: 'Capacity',
        ability: 'charisma',
        base_cost: 100,
        incremental_cost: 25,
        population_required: null,
        size_min: 3,
        size_max: 9,
        size: 3,
        tier: 1,
        capacity: 8,
        output: null,
        image_url: null,
        t2_upgrade_cost: 500,
        t3_upgrade_cost: 1500,
        speedup_multiplier: 1,
      }
      const power = {
        ...living,
        name: 'Power generator',
        category: 'Production',
        ability: 'strength',
      }
      await page.route('**/api/v1/rooms/build/', async (route) => {
        const request = route.request().postDataJSON()
        expect(request.room_name).toBe('Living room')
        built = true
        const room = {
          ...living,
          id: 'new-living',
          vault_id: 'vault-1',
          coordinate_x: request.coordinate_x,
          coordinate_y: request.coordinate_y,
        }
        builtRooms = [room]
        return route.fulfill({ json: room })
      })
      await page.route('**/api/v1/rooms/buildable/vault-1/', (route) =>
        route.fulfill({ json: [power, living] })
      )
      await page.route('**/api/v1/rooms/vault/vault-1/', (route) =>
        route.fulfill({
          json: [
            {
              ...power,
              id: 'generator',
              vault_id: 'vault-1',
              coordinate_x: 0,
              coordinate_y: 0,
            },
            ...builtRooms,
          ],
        })
      )
      await page.route('**/api/v1/objectives/vault-1/**', (route) =>
        route.fulfill({
          json: [
            {
              ...STAFFING_OBJECTIVE,
              id: 'housing',
              template_key: 'starter:build a living quarters',
              objective_type: 'build',
              sequence: 1,
              progress: built ? 1 : 0,
              total: 1,
              reward: 'dweller:Wanderer',
            },
          ],
        })
      )
      await page.reload()
      await expect(page.locator('.onboarding-card')).toContainText('Build more Living Quarters')
      await page.getByRole('button', { name: 'Build B', exact: true }).click()
      const menu = page.getByRole('dialog', { name: 'Room menu' })
      await expect(menu).toBeVisible()
      const livingRoom = menu.locator('[data-onboarding="build-living-room"]')
      const spotlight = page.locator('.onboarding-cutout--modal')
      await expect(spotlight).toBeVisible()
      await expect(page.locator('.onboarding-card--modal')).toHaveCSS('z-index', '1002')
      await expect
        .poll(async () => {
          const target = await livingRoom.boundingBox()
          const bounds = await spotlight.boundingBox()
          return (
            !!target &&
            !!bounds &&
            Math.abs(target.x - bounds.x - 4) < 2 &&
            Math.abs(target.y - bounds.y - 4) < 2
          )
        })
        .toBe(true)
      const search = menu.getByRole('searchbox', { name: 'Search rooms' })
      await search.fill(' POWER ')
      await expect(livingRoom).toHaveCount(0)
      await expect(page.locator('.onboarding-card--modal')).toBeVisible()
      await search.fill('not-a-room')
      await expect(menu.getByRole('status')).toHaveText('No rooms match your search.')
      await menu.getByRole('button', { name: 'Clear room search' }).click()
      await expect(livingRoom).toBeVisible()
      await page.screenshot({ path: test.info().outputPath('housing-menu.png') })
      await search.fill('living')
      await expect(menu.locator('.room-menu-item')).toHaveCount(1)
      await livingRoom.focus()
      await page.keyboard.press('Enter')
      await expect(menu).toHaveCount(0)
      const placement = page.locator('[data-onboarding="build-living-room-slot"]').first()
      await expect(placement).toBeVisible()
      await expect(page.locator('.onboarding-cutout')).toBeVisible()
      expect(built).toBe(false)
      await placement.click()
      await expect.poll(() => built).toBe(true)
      await expect(page.getByRole('button', { name: 'Claim dweller:Wanderer' })).toBeVisible()
      await expect(page.locator('.onboarding-cutout')).toHaveCount(0)
      // Building earns the reward; selecting and explaining never claims it.
      const ledger = await page.evaluate(() =>
        JSON.parse(localStorage.getItem('onboarding:v1') ?? '{}')
      )
      expect(ledger['vault-1'].teaching.lessons['orientation.housing']).toBeUndefined()
    })
  }

  test('a housing claim welcomes the dweller and hands off to the roster', async ({ page }) => {
    await openVault(page, ORIENTATION_ACKNOWLEDGED)
    let completed = false
    const housing = {
      ...STAFFING_OBJECTIVE,
      id: 'housing',
      challenge: 'Build a Living Quarters',
      template_key: 'starter:build a living quarters#v2',
      objective_type: 'build',
      target_entity: { room_type: 'living_room' },
      progress: 1,
      total: 1,
      reward: 'dweller:Wanderer',
    }
    await page.route('**/api/v1/objectives/vault-1/**', async (route) => {
      if (route.request().url().endsWith('/housing/claim')) {
        completed = true
        return route.fulfill({ json: { progress: 1, total: 1, is_completed: true } })
      }
      return route.fulfill({ json: [{ ...housing, is_completed: completed }] })
    })
    await page.goto('/vault/vault-1/objectives')
    await page.getByRole('button', { name: 'Claim Reward', exact: true }).click()
    const celebration = page.getByRole('dialog', { name: 'Objective Complete!' })
    await expect(celebration).toContainText('Wanderer has joined your vault')
    await celebration.getByRole('button', { name: 'View dwellers' }).click()
    await expect(page).toHaveURL(/\/vault\/vault-1\/dwellers$/)
    await expect(celebration).toHaveCount(0)
  })

  test('the first-expedition handoff offers one task and stays dismissed after reload', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    const teaching = {
      ...ORIENTATION_ACKNOWLEDGED,
      lessons: {
        ...ORIENTATION_ACKNOWLEDGED.lessons,
        'orientation.staffing': 'acknowledged',
        'orientation.housing': 'acknowledged',
        'orientation.departure': 'acknowledged',
      },
    }
    await openVault(page, teaching)
    await page.route('**/api/v1/objectives/vault-1/**', (route) =>
      route.fulfill({
        json: [
          {
            ...STAFFING_OBJECTIVE,
            id: 'departure',
            template_key: 'starter:send a dweller exploring',
            objective_type: 'explore',
            progress: 1,
            total: 1,
            is_completed: true,
          },
        ],
      })
    )
    await page.route('**/api/v1/explorations/vault/vault-1?*', (route) =>
      route.fulfill({
        json: [
          {
            id: 'first-run',
            vault_id: 'vault-1',
            dweller_id: 'wanderer',
            status: 'active',
            duration: 1,
            start_time: new Date().toISOString(),
          },
        ],
      })
    )
    await page.route('**/api/v1/storage/vault/vault-1/items', (route) =>
      route.fulfill({
        json: {
          weapons: [{ id: 'weapon', dweller_id: null }],
          outfits: [],
          items: [],
          junk: [],
          pets: [],
        },
      })
    )
    await page.reload()
    const handoff = page.getByRole('region', { name: 'First expedition handoff' })
    await expect(handoff).toContainText('While they’re away')
    await expect(handoff.getByRole('button', { name: 'Review equipment' })).toBeVisible()
    await expect(page.locator('.onboarding-cutout')).toHaveCount(0)
    await page.getByRole('button', { name: 'Notifications' }).click()
    await expect(page.getByRole('dialog', { name: 'Notifications' })).toBeVisible()
    await expect(handoff).toBeHidden()
    await page.keyboard.press('Escape')
    await expect(handoff).toBeVisible()
    await handoff.getByRole('button', { name: 'Finish intro' }).click()
    await expect(handoff).toHaveCount(0)
    await page.reload()
    await expect(page.getByText('Vault 42', { exact: true }).first()).toBeVisible()
    await expect(handoff).toHaveCount(0)
  })
})
