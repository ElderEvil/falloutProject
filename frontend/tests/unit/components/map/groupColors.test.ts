import { describe, expect, it } from 'vite-plus/test'
import { GROUP_FAMILIES, familyFor, groupColor } from '@/modules/map/models/groupColors'

// Mirrors backend/app/data/places/place_groups.json. If a group is added there and
// not here, its markers silently lose their tint — so the list is asserted.
const CATALOG_GROUPS = [
  'settlement',
  'city',
  'gas_station',
  'supermarket',
  'factory',
  'metro',
  'military',
  'brotherhood_outpost',
  'research',
  'power',
  'entertainment',
  'landmark',
  'vault_tec',
  'ruin',
  'region',
  'exclusion_zone',
  'wasteland_site',
  'vertical_refuge',
  'observation_facility',
]

describe('groupColors', () => {
  it('gives every catalog group a family', () => {
    const unmapped = CATALOG_GROUPS.filter((key) => familyFor(key) === undefined)
    expect(unmapped).toEqual([])
  })

  it('collapses nineteen groups onto five families', () => {
    const families = new Set(CATALOG_GROUPS.map((key) => familyFor(key)))
    expect(families.size).toBe(5)
    expect(new Set(Object.keys(GROUP_FAMILIES))).toEqual(families)
  })

  it('resolves a colour for every mapped group', () => {
    for (const key of CATALOG_GROUPS) {
      expect(groupColor(key)).toMatch(/^var\(--color-family-[a-z]+\)$/)
    }
  })

  it('leaves ungrouped and unknown keys untinted', () => {
    expect(groupColor(null)).toBeUndefined()
    expect(groupColor(undefined)).toBeUndefined()
    expect(groupColor('not_a_group')).toBeUndefined()
    expect(familyFor('')).toBeUndefined()
  })

  it('puts threats and sanctuaries in different families', () => {
    // The one distinction the map must never blur.
    expect(familyFor('military')).toBe('threat')
    expect(familyFor('wasteland_site')).toBe('threat')
    expect(familyFor('settlement')).toBe('civil')
    expect(groupColor('military')).not.toBe(groupColor('settlement'))
  })
})
