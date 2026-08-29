import type { components } from '@/core/types/api.generated'

// Re-export generated API types
// Dweller is the full type with all relations (vault, room, weapon, outfit)
export type Dweller = components['schemas']['DwellerReadFull']
export type DwellerFull = components['schemas']['DwellerReadFull']
/** Full dweller details used by exploration cards and timelines. */
export type DetailedDweller = DwellerFull
export type DwellerShort = components['schemas']['DwellerReadLess']
export type DwellerCreate = components['schemas']['DwellerCreate']
export type DwellerUpdate = components['schemas']['DwellerUpdate']

// Single source of truth shared by DwellerBio and the detail container (relocated from a component export).
export interface MapPlaceLink {
  name: string
  locationId: string
}

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

// Weights mirror backend game_config.combat (dweller_strength_weight etc.).
// Weapon damage is omitted: DwellerShort does not carry weapon data.
const COMBAT_WEIGHTS = { strength: 0.4, endurance: 0.3, agility: 0.3 } as const
const LEVEL_POWER_BONUS = 2

export function getCombatPower(dweller: Pick<DwellerShort, 'strength' | 'endurance' | 'agility' | 'level'>): number {
  return Math.round(
    dweller.strength * COMBAT_WEIGHTS.strength +
      dweller.endurance * COMBAT_WEIGHTS.endurance +
      dweller.agility * COMBAT_WEIGHTS.agility +
      dweller.level * LEVEL_POWER_BONUS
  )
}

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
  charisma: {
    icon: 'mdi:account-voice',
    letter: 'C',
    label: 'Charisma',
    resourceName: 'Resources',
  },
  intelligence: {
    icon: 'mdi:brain',
    letter: 'I',
    label: 'Intelligence',
    resourceName: 'Resources',
  },
  agility: { icon: 'mdi:food-drumstick', letter: 'A', label: 'Agility', resourceName: 'Food' },
  luck: { icon: 'mdi:clover', letter: 'L', label: 'Luck', resourceName: 'Resources' },
}

export function getAbilityConfig(ability: string | null | undefined): AbilityConfig | null {
  if (!ability) return null
  return ABILITY_CONFIG[ability.toLowerCase() as SpecialKey] ?? null
}

/** Visual attributes type — generated from backend OpenAPI schema. */
export type VisualAttributes = components['schemas']['DwellerVisualAttributes']

/** Icon mapping for death causes */
export const DEATH_CAUSE_ICON_MAP: Record<string, string> = {
  health: 'mdi:heart-broken',
  radiation: 'mdi:radioactive',
  incident: 'mdi:fire',
  exploration: 'mdi:compass',
  combat: 'mdi:sword',
}

/** Get the icon for a death cause, defaulting to skull */
export function getDeathCauseIcon(deathCause: string | null | undefined): string {
  if (!deathCause) return 'mdi:skull'
  return DEATH_CAUSE_ICON_MAP[deathCause] ?? 'mdi:skull'
}

/** Status badge configuration */
export interface StatusConfig {
  icon: string
  label: string
  color: string
  bgColor: string
  borderColor: string
  glowColor: string
}

/** Status → display config — single source of truth for dweller status badges */
export const STATUS_CONFIG_MAP: Record<string, StatusConfig> = {
  exploring: {
    icon: 'mdi:compass-outline',
    label: 'Exploring',
    color: 'text-blue-400',
    bgColor: 'bg-blue-900/30',
    borderColor: 'border-blue-500/50',
    glowColor: 'rgb(59 130 246 / 0.3)',
  },
  questing: {
    icon: 'mdi:sword-cross',
    label: 'Questing',
    color: 'text-orange-400',
    bgColor: 'bg-orange-900/30',
    borderColor: 'border-orange-500/50',
    glowColor: 'rgb(249 115 22 / 0.3)',
  },
  working: {
    icon: 'mdi:hammer-wrench',
    label: 'Working',
    color: 'text-green-400',
    bgColor: 'bg-green-900/30',
    borderColor: 'border-green-500/50',
    glowColor: 'rgb(34 197 94 / 0.3)',
  },
  training: {
    icon: 'mdi:dumbbell',
    label: 'Training',
    color: 'text-orange-400',
    bgColor: 'bg-orange-900/30',
    borderColor: 'border-orange-500/50',
    glowColor: 'rgb(249 115 22 / 0.3)',
  },
  resting: {
    icon: 'mdi:heart-outline',
    label: 'Socializing',
    color: 'text-pink-400',
    bgColor: 'bg-pink-900/30',
    borderColor: 'border-pink-500/50',
    glowColor: 'rgb(236 72 153 / 0.3)',
  },
  fighting: {
    icon: 'mdi:boxing-glove',
    label: 'Fighting',
    color: 'text-red-400',
    bgColor: 'bg-red-900/30',
    borderColor: 'border-red-500/50',
    glowColor: 'rgb(239 68 68 / 0.3)',
  },
  dead: {
    icon: 'mdi:skull',
    label: 'Dead',
    color: 'text-red-400',
    bgColor: 'bg-red-900/30',
    borderColor: 'border-red-500/50',
    glowColor: 'rgb(239 68 68 / 0.3)',
  },
  idle: {
    icon: 'mdi:coffee-outline',
    label: 'Idle',
    color: 'text-yellow-400',
    bgColor: 'bg-yellow-900/30',
    borderColor: 'border-yellow-500/50',
    glowColor: 'rgb(234 179 8 / 0.3)',
  },
  unknown: {
    icon: 'mdi:help-circle-outline',
    label: 'Unknown',
    color: 'text-gray-400',
    bgColor: 'bg-gray-900/30',
    borderColor: 'border-gray-500/50',
    glowColor: 'rgb(107 114 128 / 0.3)',
  },
}

/** Get status config, defaulting to unknown */
export function getStatusConfig(status: string | null | undefined): StatusConfig {
  if (!status) return STATUS_CONFIG_MAP.unknown!
  return STATUS_CONFIG_MAP[status] ?? STATUS_CONFIG_MAP.unknown!
}
