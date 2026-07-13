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
    glowColor: 'shadow-blue-500/30',
  },
  questing: {
    icon: 'mdi:sword-cross',
    label: 'Questing',
    color: 'text-orange-400',
    bgColor: 'bg-orange-900/30',
    borderColor: 'border-orange-500/50',
    glowColor: 'shadow-orange-500/30',
  },
  working: {
    icon: 'mdi:hammer-wrench',
    label: 'Working',
    color: 'text-green-400',
    bgColor: 'bg-green-900/30',
    borderColor: 'border-green-500/50',
    glowColor: 'shadow-green-500/30',
  },
  training: {
    icon: 'mdi:dumbbell',
    label: 'Training',
    color: 'text-orange-400',
    bgColor: 'bg-orange-900/30',
    borderColor: 'border-orange-500/50',
    glowColor: 'shadow-orange-500/30',
  },
  dead: {
    icon: 'mdi:skull',
    label: 'Dead',
    color: 'text-red-400',
    bgColor: 'bg-red-900/30',
    borderColor: 'border-red-500/50',
    glowColor: 'shadow-red-500/30',
  },
  idle: {
    icon: 'mdi:coffee-outline',
    label: 'Idle',
    color: 'text-yellow-400',
    bgColor: 'bg-yellow-900/30',
    borderColor: 'border-yellow-500/50',
    glowColor: 'shadow-yellow-500/30',
  },
  unknown: {
    icon: 'mdi:help-circle-outline',
    label: 'Unknown',
    color: 'text-gray-400',
    bgColor: 'bg-gray-900/30',
    borderColor: 'border-gray-500/50',
    glowColor: 'shadow-gray-500/30',
  },
}

/** Get status config, defaulting to unknown */
export function getStatusConfig(status: string | null | undefined): StatusConfig {
  if (!status) return STATUS_CONFIG_MAP.unknown!
  return STATUS_CONFIG_MAP[status] ?? STATUS_CONFIG_MAP.unknown!
}
