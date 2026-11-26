import { describe, it, expect } from 'vite-plus/test'
import {
  EXPEDITION_SITE_ICON,
  MARKER_TYPES,
  locationMarkerIcon,
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

  it.each([
    ['discovery', 'mdi:map-marker-question', 'Discovery'],
    ['expedition_site', EXPEDITION_SITE_ICON, 'Expedition Sites'],
  ])('returns the registry icon and label for %s', (type, icon, label) => {
    expect(markerTypeMeta(type)).toEqual({ type, icon, label })
  })

  it('shares the expedition-site icon constant with the registry', () => {
    expect(EXPEDITION_SITE_ICON).toBe('mdi:map-marker-star')
    expect(markerTypeMeta('expedition_site').icon).toBe(EXPEDITION_SITE_ICON)
  })

  it('falls back to a generic marker for an unknown type', () => {
    const meta = markerTypeMeta('mystery')
    expect(meta.icon).toBe('mdi:map-marker')
    expect(meta.label).toBe('mystery')
  })

  it('prefers the site-type archetype icon when the location has one', () => {
    const icons = new Map([['gas_station', 'mdi:gas-station']])
    expect(locationMarkerIcon('discovery', 'gas_station', icons)).toBe('mdi:gas-station')
  })

  it('falls back to the neutral place glyph without an archetype', () => {
    const icons = new Map([['gas_station', 'mdi:gas-station']])
    expect(locationMarkerIcon('discovery', null, icons)).toBe('mdi:map-marker-outline')
    expect(locationMarkerIcon('origin', 'unknown_group', icons)).toBe('mdi:map-marker-outline')
    expect(locationMarkerIcon('visited', null, icons)).toBe('mdi:map-marker-outline')
  })

  it('keeps the semantic icon for vaults and home vaults', () => {
    const icons = new Map<string, string>()
    expect(locationMarkerIcon('home_vault', null, icons)).toBe('mdi:home-city')
    expect(locationMarkerIcon('vault', null, icons)).toBe('mdi:radioactive')
  })
})
