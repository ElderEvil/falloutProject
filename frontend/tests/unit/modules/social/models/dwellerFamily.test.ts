import { describe, expect, it } from 'vite-plus/test'
import { generationOf } from '@/modules/social/models/dwellerFamily'
import { makeDweller } from '../../../helpers/dwellerFixtures'

const dweller = (id: string, parent1?: string, parent2?: string) =>
  makeDweller({
    id,
    first_name: id,
    last_name: null,
    parent_1_id: parent1 ?? null,
    parent_2_id: parent2 ?? null,
  })

const founders = [dweller('f1'), dweller('f2')]
const child = dweller('c1', 'f1', 'f2')
const grandchild = dweller('g1', 'c1', 'f2')

describe('generationOf', () => {
  it.each([
    ['counts founders with no in-vault parents as generation 1', founders, 'f1', 1],
    ['counts founders with no in-vault parents as generation 1', founders, 'f2', 1],
    ['counts a child of two founders as generation 2', [...founders, child], 'c1', 2],
    ['counts a grandchild as generation 3', [...founders, child, grandchild], 'g1', 3],
    [
      'is partner-independent: generation follows only the dweller own parents',
      [...founders, child],
      'f2',
      1,
    ],
    ['ignores parent ids not present in the list', [dweller('o1', 'missing-parent')], 'o1', 1],
    ['returns 1 for a dweller id not in the list', founders, 'ghost', 1],
  ] as const)('%s', (_name, roster, id, generation) => {
    expect(generationOf(roster, id)).toBe(generation)
  })

  it('terminates on parent cycles', () => {
    const a = dweller('a', 'b')
    const b = dweller('b', 'a')

    expect(generationOf([a, b], 'a')).toBeGreaterThanOrEqual(1)
    expect(generationOf([a, b], 'b')).toBeGreaterThanOrEqual(1)
  })
})
