import { describe, it, expect } from 'vitest'
import { MARKER_TYPES, markerTypeMeta } from '@/modules/map/models/markerTypeMeta'

describe('markerTypeMeta', () => {
  it('exposes the five marker types in display order', () => {
    expect(MARKER_TYPES.map((meta) => meta.type)).toEqual([
      'home_vault',
      'origin',
      'visited',
      'discovery',
      'vault',
    ])
  })

  it('returns icon and label for a known type', () => {
    expect(markerTypeMeta('discovery')).toEqual({
      type: 'discovery',
      icon: 'mdi:compass',
      label: 'Discovery',
    })
  })

  it('falls back to a generic marker for an unknown type', () => {
    const meta = markerTypeMeta('mystery')
    expect(meta.icon).toBe('mdi:map-marker')
    expect(meta.label).toBe('mystery')
  })
})
