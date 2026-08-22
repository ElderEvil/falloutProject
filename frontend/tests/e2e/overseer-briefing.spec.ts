import { test, expect } from '@playwright/test'
import type { Page } from '@playwright/test'
import { setAuthToken } from './fixtures/auth'

const vault = {
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
  radio_mode: 'recruitment',
  created_at: '2026-08-22T00:00:00Z',
  updated_at: '2026-08-22T00:00:00Z',
  resource_warnings: [{ type: 'critical_water', message: 'Water reserves are critical' }],
  room_count: 1,
  dweller_count: 8,
  stimpack: 4,
  radaway: 2,
}

const dwellers = [
  {
    id: 'dweller-1',
    first_name: 'Ada',
    last_name: 'Wells',
    thumbnail_url: null,
    level: 4,
    health: 100,
    max_health: 100,
    radiation: 0,
    happiness: 90,
    room_id: null,
    status: 'exploring',
    is_adult: true,
    age_group: 'adult',
    gender: 'female',
    strength: 5,
    perception: 6,
    endurance: 5,
    charisma: 4,
    intelligence: 7,
    agility: 6,
    luck: 4,
  },
  {
    id: 'dweller-2',
    first_name: 'Boone',
    last_name: 'Cole',
    thumbnail_url: null,
    level: 3,
    health: 100,
    max_health: 100,
    radiation: 0,
    happiness: 76,
    room_id: null,
    status: 'exploring',
    is_adult: true,
    age_group: 'adult',
    gender: 'male',
    strength: 7,
    perception: 5,
    endurance: 6,
    charisma: 3,
    intelligence: 4,
    agility: 5,
    luck: 4,
  },
  {
    id: 'dweller-3',
    first_name: 'Casey',
    last_name: 'Stone',
    thumbnail_url: null,
    level: 5,
    health: 100,
    max_health: 100,
    radiation: 0,
    happiness: 80,
    room_id: 'room-1',
    status: 'training',
    is_adult: true,
    age_group: 'adult',
    gender: 'female',
    strength: 6,
    perception: 5,
    endurance: 7,
    charisma: 4,
    intelligence: 6,
    agility: 5,
    luck: 5,
  },
]

const explorations = ['dweller-1', 'dweller-2'].map((dwellerId, index) => ({
  id: `exploration-${index + 1}`,
  vault_id: 'vault-1',
  dweller_id: dwellerId,
  status: 'active',
  start_time: '2026-08-22T00:00:00Z',
  end_time: null,
  duration: 8,
  events: [],
  loot_collected: [],
  total_distance: 12,
  total_caps_found: 20,
  enemies_encountered: 1,
  created_at: '2026-08-22T00:00:00Z',
  updated_at: '2026-08-22T00:00:00Z',
  dweller_strength: 5,
  dweller_perception: 5,
  dweller_endurance: 5,
  dweller_charisma: 5,
  dweller_intelligence: 5,
  dweller_agility: 5,
  dweller_luck: 5,
  stimpaks: 1,
  radaways: 0,
}))

const incidents = ['incident-1', 'incident-2'].map((id, index) => ({
  id,
  vault_id: 'vault-1',
  room_id: 'room-1',
  type: index ? 'radroach_infestation' : 'raider_attack',
  status: 'active',
  difficulty: 3,
  start_time: '2026-08-22T00:00:00Z',
  end_time: null,
  duration: 600,
  elapsed_time: 90,
  damage_dealt: 10,
  enemies_defeated: 1,
  loot: null,
  rooms_affected: ['room-1'],
  spread_count: 0,
  created_at: '2026-08-22T00:00:00Z',
  updated_at: '2026-08-22T00:00:00Z',
}))

const rooms = [
  {
    id: 'overseer-office',
    vault_id: 'vault-1',
    name: "Overseer's Office",
    category: 'quests',
    ability: null,
    tier: 1,
    capacity: 0,
    size: 6,
    size_min: 6,
    size_max: 6,
    coordinate_x: 0,
    coordinate_y: 0,
    image_url: null,
    t2_upgrade_cost: 3500,
    t3_upgrade_cost: 15000,
  },
]

async function mockVaultApi(page: Page) {
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname

    if (path === '/api/v1/vaults/my') return route.fulfill({ json: [vault] })
    if (path === '/api/v1/vaults/vault-1') return route.fulfill({ json: vault })
    if (path === '/api/v1/rooms/vault/vault-1/') return route.fulfill({ json: rooms })
    if (path === '/api/v1/dwellers/vault/vault-1/') return route.fulfill({ json: dwellers })
    if (path.startsWith('/api/v1/dwellers/')) {
      return route.fulfill({ json: { ...dwellers.find((dweller) => path.endsWith(dweller.id)), weapon: null, outfit: null } })
    }
    if (path === '/api/v1/explorations/vault/vault-1') return route.fulfill({ json: explorations })
    if (path === '/api/v1/game/vaults/vault-1/game-state') {
      return route.fulfill({ json: { is_paused: true, total_game_time: 3600, paused_at: null } })
    }
    if (path === '/api/v1/game/vaults/vault-1/incidents') {
      return route.fulfill({
        json: {
          vault_id: 'vault-1',
          incident_count: incidents.length,
          incidents: incidents.map(({ id, type, status, room_id, difficulty, start_time, elapsed_time, damage_dealt, enemies_defeated }) => ({
            id,
            type,
            status,
            room_id,
            difficulty,
            start_time,
            elapsed_time,
            damage_dealt,
            enemies_defeated,
          })),
        },
      })
    }
    if (path.startsWith('/api/v1/game/vaults/vault-1/incidents/')) {
      const incident = incidents.find(({ id }) => path.endsWith(id)) ?? incidents[0]
      return route.fulfill({ json: incident })
    }
    if (path === '/api/v1/notifications/unread-count') return route.fulfill({ json: { count: 0 } })
    if (path === '/api/v1/notifications/') return route.fulfill({ json: [] })
    if (path.startsWith('/api/v1/stream/')) {
      return route.fulfill({ contentType: 'text/event-stream', body: ': connected\n\n' })
    }

    throw new Error(`Unhandled API request: ${route.request().method()} ${path}`)
  })
}

test('authenticated vault route keeps the briefing in the Overseer’s Office', async ({ page }) => {
  await mockVaultApi(page)
  await page.goto('/login')
  await setAuthToken(page, 'deterministic-e2e-token')
  await page.goto('/vault/vault-1')

  await expect(page.locator('.overseer-briefing')).toHaveCount(0)

  await page.getByRole('button', { name: /Overseer's Office/i }).click()
  const briefing = page.locator('.overseer-briefing')
  await expect(briefing).toBeVisible()
  await expect(briefing).toContainText('VAULT STATUS')
  await expect(briefing).toContainText('VAULT 42')
  await expect(briefing).toContainText('2 INCIDENTS REQUIRE RESPONSE')
  await expect(briefing).toContainText('3 active operations')
  await expect(briefing).toContainText('Water reserves are critical')

  await briefing.getByRole('button', { name: 'Respond to active incidents' }).click()
  await expect(page.getByText('>> LOCATION')).toBeVisible()
})
