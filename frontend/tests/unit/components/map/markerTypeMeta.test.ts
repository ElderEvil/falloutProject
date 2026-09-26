import { describe, it, expect } from 'vitest'
import {
  EXPEDITION_SITE_ICON,
  MARKER_TYPES,
  markerTypeMeta,
} from '@/modules/map/models/markerTypeMeta'

describe('markerTypeMeta', () => {
  it('exposes the six marker types in display order', () => {
    expect(MARKER_TYPES.map((meta) => meta.type)).toEqual([
      'home_vault',
      'origin',
      'visited',
      'discovery',
      'vault',
      'expedition_site',
    ])
  })

  it('returns icon and label for a known type', () => {
    expect(markerTypeMeta('discovery')).toEqual({
      type: 'discovery',
      icon: 'mdi:compass',
      label: 'Discovery',
    })
  })

  it('returns the expedition-site registry entry', () => {
    expect(markerTypeMeta('expedition_site')).toEqual({
      type: 'expedition_site',
      icon: 'mdi:map-marker-star',
      label: 'Expedition Sites',
    })
  })

  it('falls back to a generic marker for an unknown type', () => {
    const meta = markerTypeMeta('mystery')
    expect(meta.icon).toBe('mdi:map-marker')
    expect(meta.label).toBe('mystery')
  })

  it('uses the shared expedition-site icon constant in the registry', () => {
    expect(EXPEDITION_SITE_ICON).toBe('mdi:map-marker-star')
    expect(markerTypeMeta('expedition_site').icon).toBe(EXPEDITION_SITE_ICON)
  })
})
