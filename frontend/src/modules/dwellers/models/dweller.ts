import type { components } from '@/core/types/api.generated'

// Re-export generated API types
// Dweller is the full type with all relations (vault, room, weapon, outfit)
export type Dweller = components['schemas']['DwellerReadFull']
export type DwellerFull = components['schemas']['DwellerReadFull']
export type DwellerShort = components['schemas']['DwellerReadLess']
export type DwellerCreate = components['schemas']['DwellerCreate']
export type DwellerUpdate = components['schemas']['DwellerUpdate']

// Death system types
export type DeathCause = components['schemas']['DeathCauseEnum']
export type DwellerDead = components['schemas']['DwellerDeadRead']
export type DwellerReviveResponse = components['schemas']['DwellerReviveResponse']
export type RevivalCostResponse = components['schemas']['RevivalCostResponse']

// Helper type for SPECIAL stats
export interface Special {
  strength: number
  perception: number
  endurance: number
  charisma: number
  intelligence: number
  agility: number
  luck: number
}

/** Visual attributes type — generated from backend OpenAPI schema. */
export type VisualAttributes = components['schemas']['DwellerVisualAttributes']
