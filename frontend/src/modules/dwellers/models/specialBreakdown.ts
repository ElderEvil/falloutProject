import type { Dweller } from './dweller'

export type SpecialLetter = 'S' | 'P' | 'E' | 'C' | 'I' | 'A' | 'L'

type SpecialStat = 'strength' | 'perception' | 'endurance' | 'charisma' | 'intelligence' | 'agility' | 'luck'

export interface SpecialBreakdown {
  letter: SpecialLetter
  label: string
  base: number
  identity: number
  outfit: number
  outfitName: string | null
  effective: number
}

const LETTER_DEFS: Array<{ letter: SpecialLetter; label: string; stat: SpecialStat }> = [
  { letter: 'S', label: 'Strength', stat: 'strength' },
  { letter: 'P', label: 'Perception', stat: 'perception' },
  { letter: 'E', label: 'Endurance', stat: 'endurance' },
  { letter: 'C', label: 'Charisma', stat: 'charisma' },
  { letter: 'I', label: 'Intelligence', stat: 'intelligence' },
  { letter: 'A', label: 'Agility', stat: 'agility' },
  { letter: 'L', label: 'Luck', stat: 'luck' },
]

type BreakdownInput = Pick<Dweller, SpecialLetter | 'outfit' | 'identity_modifiers'>

/**
 * Per-stat base vs effective breakdown, mirroring backend
 * ``options.identity_modifiers.effective_stat``: stored + identity + outfit,
 * floored at 1, never capped, never persisted.
 */
export function getSpecialBreakdown(dweller: BreakdownInput | null | undefined): SpecialBreakdown[] {
  if (!dweller) return []
  return LETTER_DEFS.map(({ letter, label, stat }) => {
    const base = dweller[letter] ?? 0
    const identity = dweller.identity_modifiers?.[stat] ?? 0
    const outfit = dweller.outfit?.[stat] ?? 0
    return {
      letter,
      label,
      base,
      identity,
      outfit,
      outfitName: outfit !== 0 ? (dweller.outfit?.name ?? null) : null,
      effective: Math.max(1, base + identity + outfit),
    }
  })
}

/** Human-readable bonus sources, e.g. "+5 Vault Suit", "+2 identity". Empty when clean. */
export function describeBonusSources(breakdown: SpecialBreakdown): string[] {
  const parts: string[] = []
  if (breakdown.outfit !== 0 && breakdown.outfitName) {
    parts.push(`${breakdown.outfit > 0 ? '+' : ''}${breakdown.outfit} ${breakdown.outfitName}`)
  }
  if (breakdown.identity !== 0) {
    parts.push(`${breakdown.identity > 0 ? '+' : ''}${breakdown.identity} identity`)
  }
  return parts
}
