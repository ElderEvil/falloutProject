import type { DwellerShort } from '@/modules/dwellers/models/dweller'

/**
 * Roster fixture: a working adult with a full SPECIAL spread, so a suite only
 * spells out the fields its behaviour depends on.
 */
export function makeDweller(overrides: Record<string, unknown> = {}): DwellerShort {
  return {
    id: 'dweller-1',
    first_name: 'Sarah',
    last_name: 'Lyons',
    thumbnail_url: null,
    level: 5,
    health: 80,
    max_health: 100,
    radiation: 0,
    happiness: 75,
    room_id: null,
    status: 'working',
    age_group: 'adult',
    gender: 'female',
    rarity: 'rare',
    strength: 8,
    perception: 4,
    endurance: 4,
    charisma: 4,
    intelligence: 4,
    agility: 4,
    luck: 4,
    ...overrides,
  } as DwellerShort
}
