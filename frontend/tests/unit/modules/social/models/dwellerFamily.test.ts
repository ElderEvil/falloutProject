import { describe, expect, it } from 'vitest'
import { generationOf } from '@/modules/social/models/dwellerFamily'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'

function dweller(id: string, parent1?: string | null, parent2?: string | null): DwellerShort {
  return {
    id,
    first_name: id,
    last_name: null,
    level: 1,
    thumbnail_url: null,
    age_group: 'adult',
    gender: 'female',
    rarity: 'common',
    health: 100,
    max_health: 100,
    happiness: 50,
    strength: 1,
    perception: 1,
    endurance: 1,
    charisma: 1,
    intelligence: 1,
    agility: 1,
    luck: 1,
    parent_1_id: parent1 ?? null,
    parent_2_id: parent2 ?? null,
  } as DwellerShort
}

describe('generationOf', () => {
  const founders = [dweller('f1'), dweller('f2')]
  const child = dweller('c1', 'f1', 'f2')
  const grandchild = dweller('g1', 'c1', 'f2')

  it('counts founders with no in-vault parents as generation 1', () => {
    expect(generationOf(founders, 'f1')).toBe(1)
    expect(generationOf(founders, 'f2')).toBe(1)
  })

  it('counts a child of two founders as generation 2', () => {
    expect(generationOf([...founders, child], 'c1')).toBe(2)
  })

  it('counts a grandchild as generation 3', () => {
    expect(generationOf([...founders, child, grandchild], 'g1')).toBe(3)
  })

  it('is partner-independent: generation follows only the dweller own parents', () => {
    // c1 is a child of founders; their partner f2 is also a founder.
    expect(generationOf([...founders, child], 'c1')).toBe(2)
    expect(generationOf([...founders, child], 'f2')).toBe(1)
  })

  it('ignores parent ids not present in the list', () => {
    const orphan = dweller('o1', 'missing-parent')
    expect(generationOf([orphan], 'o1')).toBe(1)
  })

  it('returns 1 for a dweller id not in the list', () => {
    expect(generationOf(founders, 'ghost')).toBe(1)
  })

  it('terminates on parent cycles', () => {
    const a = dweller('a', 'b')
    const b = dweller('b', 'a')
    expect(generationOf([a, b], 'a')).toBeGreaterThanOrEqual(1)
    expect(generationOf([a, b], 'b')).toBeGreaterThanOrEqual(1)
  })
})
