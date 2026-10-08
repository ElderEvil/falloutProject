import { describe, expect, it } from 'vitest'
import {
  DECLUTTER_REVEAL_ZOOM,
  isMarkerVisible,
  isPrimaryMarker,
} from '@/modules/map/utils/declutter'

describe('map marker declutter', () => {
  it('always treats home vaults, discoveries, explorers and sites as primary', () => {
    for (const type of ['home_vault', 'discovery', 'explorer', 'expedition_site'] as const) {
      expect(isPrimaryMarker({ type })).toBe(true)
      expect(isMarkerVisible({ type }, 1)).toBe(true)
    }
  })

  it('keeps a selected or exploring secondary marker visible at overview zoom', () => {
    expect(isPrimaryMarker({ type: 'visited', selected: true })).toBe(true)
    expect(isMarkerVisible({ type: 'visited', selected: true }, 1)).toBe(true)
    expect(isPrimaryMarker({ type: 'origin', exploring: true })).toBe(true)
    expect(isMarkerVisible({ type: 'origin', exploring: true }, 1)).toBe(true)
  })

  it('hides secondary markers below the reveal zoom and shows them at it', () => {
    for (const type of ['vault', 'visited', 'origin'] as const) {
      expect(isPrimaryMarker({ type })).toBe(false)
      expect(isMarkerVisible({ type }, 1)).toBe(false)
      expect(isMarkerVisible({ type }, DECLUTTER_REVEAL_ZOOM - 0.1)).toBe(false)
      expect(isMarkerVisible({ type }, DECLUTTER_REVEAL_ZOOM)).toBe(true)
    }
  })
})
