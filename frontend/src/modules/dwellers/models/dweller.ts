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

/** SPECIAL attribute key names */
export type SpecialKey =
  | 'strength'
  | 'perception'
  | 'endurance'
  | 'charisma'
  | 'intelligence'
  | 'agility'
  | 'luck'

export interface AbilityConfig {
  icon: string
  letter: string
  label: string
  resourceName: string
}

/** Room ability → display config — single source of truth for icons, letters, labels. */
export const ABILITY_CONFIG: Record<SpecialKey, AbilityConfig> = {
  strength: { icon: 'mdi:lightning-bolt', letter: 'S', label: 'Strength', resourceName: 'Power' },
  perception: { icon: 'mdi:water', letter: 'P', label: 'Perception', resourceName: 'Water' },
  endurance: { icon: 'mdi:flash', letter: 'E', label: 'Endurance', resourceName: 'All Resources' },
  charisma: { icon: 'mdi:account-voice', letter: 'C', label: 'Charisma', resourceName: 'Resources' },
  intelligence: { icon: 'mdi:brain', letter: 'I', label: 'Intelligence', resourceName: 'Resources' },
  agility: { icon: 'mdi:food-drumstick', letter: 'A', label: 'Agility', resourceName: 'Food' },
  luck: { icon: 'mdi:clover', letter: 'L', label: 'Luck', resourceName: 'Resources' },
}

export function getAbilityConfig(ability: string | null | undefined): AbilityConfig | null {
  if (!ability) return null
  return ABILITY_CONFIG[ability.toLowerCase() as SpecialKey] ?? null
}

/** Visual attributes type — generated from backend OpenAPI schema. */
export type VisualAttributes = components['schemas']['DwellerVisualAttributes']
