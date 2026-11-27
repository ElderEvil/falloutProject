import { TEST_USER, type TestUser } from '../fixtures/auth'
import { json, sse, type ApiStub } from './api'

/** The signed-in overseer the mocked specs render in the navbar. */
export const AUTH_USER: TestUser = {
  id: 'test-user-id',
  username: 'overseer',
  email: 'overseer@vault-tec.com',
  is_active: true,
  is_superuser: true,
  email_verified: true,
}

export type ResourceWarning = { type: string; message: string }

/** A healthy vault: every resource above its warning band. */
export const VAULT = {
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
  created_at: '2026-01-15T10:30:00Z',
  updated_at: '2026-01-15T10:30:00Z',
  resource_warnings: [] as ResourceWarning[],
  room_count: 1,
  dweller_count: 8,
  stimpack: 4,
  radaway: 2,
}

export const vault = (overrides: Partial<typeof VAULT> = {}) => ({ ...VAULT, ...overrides })

// Completed setup keeps HomeView on the vault dashboard instead of the async
// FirstRunSetupModal, which would otherwise replace the surface under test.
export const PROFILE = {
  id: 'test-user-id',
  user_id: 'test-user-id',
  bio: 'Overseer of Vault 42',
  avatar_url: null,
  preferences: { setup: { version: 1, completed: true, skipped: false } } as unknown,
  total_dwellers_created: 42,
  total_caps_earned: 15234,
  total_explorations: 17,
  total_rooms_built: 26,
  total_incidents: 11,
  total_incidents_won: 7,
  total_incidents_lost: 4,
  total_dwellers_born: 9,
  total_dwellers_died: 4,
  deaths_by_health: 1,
  deaths_by_radiation: 1,
  deaths_by_incident: 1,
  deaths_by_exploration: 1,
  deaths_by_combat: 0,
  created_at: '2026-01-15T10:30:00Z',
  updated_at: '2026-02-01T08:00:00Z',
}

export const profile = (overrides: Partial<typeof PROFILE> = {}) => ({ ...PROFILE, ...overrides })

export const DEATH_STATISTICS = {
  total_dwellers_born: 9,
  total_dwellers_died: 4,
  deaths_by_cause: { health: 1, radiation: 1, incident: 1, exploration: 1, combat: 0 },
  revivable_count: 2,
  permanently_dead_count: 2,
}

export const deathStatistics = (overrides: Partial<typeof DEATH_STATISTICS> = {}) => ({
  ...DEATH_STATISTICS,
  ...overrides,
})

/** The room-grid contract the frontend reads from `/rooms/grid-config/`. */
export const GRID_CONFIG = {
  units_per_room: 3,
  elevator_units: 1,
  floor_units: 3,
  shaft_x: 3,
  left_slot_starts: [0, 1, 2, 4, 5, 6],
  right_slot_starts: [9, 10, 11, 13, 14, 15],
  y_max: 25,
  build_y_max: 24,
}

/** The signed-in player the interaction/navbar specs render. */
export const PLAYER: TestUser = { ...TEST_USER, username: 'Overseer' }

export interface StandardApiOptions {
  /** Signed-in user, or `null` for the 401 an anonymous session gets. */
  user?: TestUser | null
  profile?: unknown
  statistics?: unknown
  vaults?: unknown[]
  /** Stubs tried before the standard set, so a spec can override any endpoint. */
  extra?: ApiStub[]
}

/**
 * The endpoint set almost every routed spec answers: session, profile, vault
 * list, notification counters and the SSE stream that keeps the client quiet.
 */
export const standardApi = (options: StandardApiOptions = {}): ApiStub[] => {
  const user = options.user === undefined ? AUTH_USER : options.user
  return [
    ...(options.extra ?? []),
    {
      path: '/api/v1/users/me',
      reply: user === null ? json({ detail: 'Not authenticated' }, 401) : json(user),
    },
    { path: '/api/v1/users/me/profile', reply: json(options.profile ?? PROFILE) },
    {
      path: '/api/v1/users/me/profile/statistics',
      reply: json(options.statistics ?? DEATH_STATISTICS),
    },
    {
      path: '/api/v1/auth/oauth/providers',
      reply: json({ google: false, github: false }),
    },
    { path: '/api/v1/vaults/my', reply: json(options.vaults ?? (user ? [VAULT] : [])) },
    { path: '/api/v1/notifications/unread-count', reply: json({ count: 0 }) },
    { path: '/api/v1/notifications/', reply: json([]) },
    { prefix: '/api/v1/stream/', reply: sse() },
  ]
}
