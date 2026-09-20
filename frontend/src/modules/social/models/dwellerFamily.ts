/**
 * TypeScript models for dweller family derivation (children of the vault and of a couple).
 */

import type { DwellerShort } from '@/modules/dwellers/models/dweller'

export function isChild(dweller: DwellerShort): boolean {
  return dweller.age_group === 'child'
}

export function allChildren(dwellers: readonly DwellerShort[]): DwellerShort[] {
  return dwellers.filter(isChild)
}

export function childrenOfCouple(
  dwellers: readonly DwellerShort[],
  parent1Id: string,
  parent2Id: string
): DwellerShort[] {
  return dwellers.filter(
    (d) =>
      (d.parent_1_id === parent1Id && d.parent_2_id === parent2Id) ||
      (d.parent_1_id === parent2Id && d.parent_2_id === parent1Id)
  )
}
