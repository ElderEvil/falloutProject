import type { components } from '@/core/types/api.generated'

// Pet types derived from the generated API schema — never hand-defined.
export type Pet = components['schemas']['PetRead']
export type PetEffect = components['schemas']['PetEffectRead']

export interface PetBonus {
  label: string
  value: string
}

// SPECIAL stat keys -> display labels, mirroring the outfit bonus rows.
const SPECIAL_LABELS: Record<string, string> = {
  strength: 'Strength',
  perception: 'Perception',
  endurance: 'Endurance',
  charisma: 'Charisma',
  intelligence: 'Intelligence',
  agility: 'Agility',
  luck: 'Luck',
}

// Fractional (0-1) effect keys -> display labels; rendered as +X%.
const PERCENT_LABELS: Record<string, string> = {
  damage_pct: 'Damage',
  incident_response_pct: 'Incident response',
  radiation_resist_pct: 'RAD resist',
  happiness: 'Happiness',
  caps_pct: 'Caps',
  xp_pct: 'XP',
  training_speed_pct: 'Training speed',
}

/**
 * Concise bonus chips for a pet's catalog-resolved effect: SPECIAL ints,
 * `+N max HP`, and the fractional fields as `+X%`. Zero-valued effects are
 * omitted so a neutral pet renders no chips.
 */
export function getPetBonuses(effect: PetEffect): PetBonus[] {
  const bonuses: PetBonus[] = []
  for (const [key, label] of Object.entries(SPECIAL_LABELS)) {
    const value = effect[key as keyof PetEffect] as number
    if (value > 0) bonuses.push({ label, value: `+${value}` })
  }
  if (effect.max_health > 0) bonuses.push({ label: 'Max HP', value: `+${effect.max_health}` })
  for (const [key, label] of Object.entries(PERCENT_LABELS)) {
    const value = effect[key as keyof PetEffect] as number
    if (value > 0) bonuses.push({ label, value: `+${Math.round(value * 100)}%` })
  }
  return bonuses
}