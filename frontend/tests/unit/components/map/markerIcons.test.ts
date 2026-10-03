import { describe, expect, it, vi, afterEach } from 'vitest'
import {
  ARCHETYPE_ART,
  EXPEDITION_SITE_ART,
  PROTOTYPE_KIND_ART,
  markerArtDataUrl,
} from '@/modules/map/utils/markerIcons'

function stubCanvasCtx(): CanvasRenderingContext2D {
  return new Proxy({} as CanvasRenderingContext2D, {
    get: () => () => {},
    set: () => true,
  })
}

describe('markerIcons', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('preserves every prototype kind', () => {
    expect(Object.keys(PROTOTYPE_KIND_ART).sort()).toEqual(
      [
        'abandoned_factory',
        'raider_camp',
        'radio_tower',
        'red_rocket',
        'settlement',
        'super_duper_mart',
        'supply_cache',
        'water_treatment',
      ].sort(),
    )
  })

  it('wires the mappable archetypes to prototype art', () => {
    expect(Object.keys(ARCHETYPE_ART).sort()).toEqual(
      ['factory', 'gas_station', 'settlement', 'supermarket'].sort(),
    )
  })

  it('maps expedition site ids to prototype art', () => {
    expect(EXPEDITION_SITE_ART.red_rocket).toBe(PROTOTYPE_KIND_ART.red_rocket)
    expect(EXPEDITION_SITE_ART.super_duper_mart).toBe(PROTOTYPE_KIND_ART.super_duper_mart)
  })

  it('returns null when the archetype has no preserved art', () => {
    expect(markerArtDataUrl(null)).toBeNull()
    expect(markerArtDataUrl('research')).toBeNull()
  })

  it('renders a data url for a mappable archetype', () => {
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(stubCanvasCtx())
    vi.spyOn(HTMLCanvasElement.prototype, 'toDataURL').mockReturnValue('data:image/png;base64,art')

    expect(markerArtDataUrl('gas_station')).toBe('data:image/png;base64,art')
  })
})
