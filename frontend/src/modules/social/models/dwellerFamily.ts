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

/**
 * 1-based generation of a dweller within the vault: founders with no in-vault
 * parents are generation 1, their children 2, and so on. Parent ids not present
 * in the list are ignored, results are memoized per walk, and parent cycles are
 * broken by treating the revisited dweller as a founder.
 */
export function generationOf(
  dwellers: readonly DwellerShort[],
  dwellerId: string
): number {
  const byId = new Map(dwellers.map((d) => [d.id, d]))
  const memo = new Map<string, number>()
  const visiting = new Set<string>()

  function walk(id: string): number {
    const cached = memo.get(id)
    if (cached !== undefined) return cached
    if (visiting.has(id)) return 1
    const dweller = byId.get(id)
    if (!dweller) return 1

    visiting.add(id)
    const parent1 = dweller.parent_1_id ? byId.get(dweller.parent_1_id) : undefined
    const parent2 = dweller.parent_2_id ? byId.get(dweller.parent_2_id) : undefined
    const parentGeneration = Math.max(
      parent1 ? walk(parent1.id) : 0,
      parent2 ? walk(parent2.id) : 0
    )
    visiting.delete(id)

    const generation = parentGeneration + 1
    memo.set(id, generation)
    return generation
  }

  return walk(dwellerId)
}
