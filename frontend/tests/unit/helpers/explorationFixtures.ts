import type { Exploration } from '@/modules/exploration/stores/exploration'

/** Wide exploration fixture shared by the progression/exploration suites; pass what a test varies. */
export function createExploration(overrides: Partial<Exploration> = {}): Exploration {
  return {
    id: 'exploration-1',
    vault_id: 'vault-1',
    dweller_id: 'dweller-1',
    status: 'active',
    duration: 8,
    start_time: '2026-01-01T00:00:00Z',
    end_time: null,
    events: [],
    loot_collected: [],
    total_distance: 0,
    total_caps_found: 0,
    enemies_encountered: 0,
    stimpaks: 0,
    radaways: 0,
    dweller_strength: 1,
    dweller_perception: 1,
    dweller_endurance: 1,
    dweller_charisma: 1,
    dweller_intelligence: 1,
    dweller_agility: 1,
    dweller_luck: 1,
    ...overrides,
  } as Exploration
}
