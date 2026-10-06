import { describe, it, expect } from 'vitest'
import { explorerHeading } from '@/modules/map/utils/explorerHeading'
import type { DiscoveryRouteRead, ExplorerTrack } from '@/modules/map/models/map'

function route(points: DiscoveryRouteRead['points']): DiscoveryRouteRead {
  return { exploration_id: 'expl-1', points }
}

const home = { coord_x: 0, coord_y: 0 }

describe('explorerHeading', () => {
  it('derives the heading from the last two trail points', () => {
    const track: Pick<ExplorerTrack, 'lastKnown'> = { lastKnown: null }

    const heading = explorerHeading(
      track,
      route([
        { location_id: null, coord_x: 0, coord_y: 10, timestamp: '2026-01-01T00:00:00Z' },
        { location_id: null, coord_x: 10, coord_y: 10, timestamp: '2026-01-01T01:00:00Z' },
      ]),
      home
    )

    // From (0,10) to (10,10): due east.
    expect(heading).toBe(90)
  })

  it('prefers the trail vector over the home bearing when both are available', () => {
    const track: Pick<ExplorerTrack, 'lastKnown'> = { lastKnown: { coord_x: 10, coord_y: 0 } }

    const heading = explorerHeading(
      track,
      route([
        { location_id: null, coord_x: 0, coord_y: 10, timestamp: '2026-01-01T00:00:00Z' },
        { location_id: null, coord_x: 10, coord_y: 10, timestamp: '2026-01-01T01:00:00Z' },
      ]),
      home
    )

    expect(heading).toBe(90)
  })

  it('aims home when there is no usable trail (returning run)', () => {
    const track: Pick<ExplorerTrack, 'lastKnown'> = { lastKnown: { coord_x: 10, coord_y: 0 } }

    const withoutRoute = explorerHeading(track, undefined, home)
    const shortTrail = explorerHeading(
      track,
      route([{ location_id: null, coord_x: 10, coord_y: 0, timestamp: '2026-01-01T00:00:00Z' }]),
      home
    )

    // From (10,0) toward (0,0): due west.
    expect(withoutRoute).toBe(270)
    expect(shortTrail).toBe(270)
  })

  it('returns null when neither a trail nor a position is available', () => {
    const track: Pick<ExplorerTrack, 'lastKnown'> = { lastKnown: null }

    expect(explorerHeading(track, undefined, home)).toBeNull()
    expect(explorerHeading(track, route([]), home)).toBeNull()
  })
})
