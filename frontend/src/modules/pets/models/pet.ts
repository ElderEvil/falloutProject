import type { components } from '@/core/types/api.generated'
import { getPetStats } from '@/core/models/items'

// Pet types derived from the generated API schema — never hand-defined.
export type Pet = components['schemas']['PetRead']
export type PetEffect = components['schemas']['PetEffectRead']

export interface PetBonus {
  label: string
  value: string
}

/**
 * Concise bonus chips for a pet's catalog-resolved effect: SPECIAL ints,
 * `+N max HP`, and the fractional fields as `+X%`. Zero-valued effects are
 * omitted so a neutral pet renders no chips. Formatting lives in
 * `core/models/items.getPetStats` so storage cards and pet cards agree.
 */
export function getPetBonuses(effect: PetEffect): PetBonus[] {
  return getPetStats(effect).map(({ label, value }) => ({ label, value: String(value) }))
}
