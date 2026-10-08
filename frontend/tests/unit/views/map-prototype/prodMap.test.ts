import { describe, expect, it } from 'vitest'
import { filterUnlocked, registryToCanvas, registryToTile } from '@/core/views/map-prototype/prodMap'
import type { ProdLocation } from '@/core/views/map-prototype/prodMap'

const loc = (overrides: Partial<ProdLocation> & { id: string }): ProdLocation =>
  ({
    name: 'Place',
    normalized_name: 'place',
    type: 'DISCOVERY',
    coord_x: 50,
    coord_y: 50,
    description: null,
    group_key: null,
    vault_id: 'v',
    exploration_id: null,
    created_at: null,
    clear_state: null,
    dwellers: [],
    is_unlocked: false,
    ...overrides,
  }) as ProdLocation

describe('prodMap', () => {
  it('projects registry coords to canvas pixels (exact inverse of tile-center mapping)', () => {
    expect(registryToCanvas(0)).toBe(0)
    expect(registryToCanvas(100)).toBe(640)
    expect(registryToCanvas(50)).toBe(320)
    expect(registryToCanvas(0.625)).toBe(4)
    expect(registryToCanvas(99.375)).toBe(636)
  })

  it('maps a registry anchor back to its tile (inverse of tile-center, clamped)', () => {
    expect(registryToTile(0)).toBe(0)
    expect(registryToTile(100)).toBe(79)
    expect(registryToTile(50)).toBe(40)
    for (const tile of [0, 1, 40, 78, 79]) {
      const center = ((tile + 0.5) * 100) / 80
      expect(registryToTile(center)).toBe(tile)
    }
  })

  it('keeps only unlocked locations (fail-closed on missing flag)', () => {
    const rows = [
      loc({ id: 'a', is_unlocked: true }),
      loc({ id: 'b', is_unlocked: false }),
      loc({ id: 'c' }),
    ]
    const out = filterUnlocked(rows)
    expect(out.map(l => l.id)).toEqual(['a'])
  })

  it('returns empty for empty or all-locked payloads', () => {
    expect(filterUnlocked([])).toEqual([])
    expect(filterUnlocked([loc({ id: 'x', is_unlocked: false })])).toEqual([])
  })
})
