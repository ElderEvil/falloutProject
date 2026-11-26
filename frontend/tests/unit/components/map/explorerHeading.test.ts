import { describe, it, expect } from 'vite-plus/test'
import { explorerHeading } from '@/modules/map/utils/explorerHeading'
import type { DiscoveryRouteRead, ExplorerTrack } from '@/modules/map/models/map'

function route(points: DiscoveryRouteRead['points']): DiscoveryRouteRead {
  return { exploration_id: 'expl-1', points, is_active: true }
}

const home = { coord_x: 0, coord_y: 0 }

const trailPoint = (coord_x: number, coord_y: number, hour: number) => ({
  location_id: null,
  coord_x,
  coord_y,
  timestamp: `2026-01-01T0${hour}:00:00Z`,
})

const headingFor = (
  lastKnown: Pick<ExplorerTrack, 'lastKnown'>['lastKnown'],
  points?: DiscoveryRouteRead['points']
) => explorerHeading({ lastKnown }, points ? route(points) : undefined, home)

describe('explorerHeading', () => {
  it('derives the heading from the last two trail points', () => {
    // From (0,10) to (10,10): due east.
    expect(headingFor(null, [trailPoint(0, 10, 0), trailPoint(10, 10, 1)])).toBe(90)
  })

  it('prefers the trail vector over the home bearing when both are available', () => {
    expect(
      headingFor({ coord_x: 10, coord_y: 0 }, [trailPoint(0, 10, 0), trailPoint(10, 10, 1)])
    ).toBe(90)
  })

  it('aims home when there is no usable trail (returning run)', () => {
    // From (10,0) toward (0,0): due west.
    expect(headingFor({ coord_x: 10, coord_y: 0 })).toBe(270)
    expect(headingFor({ coord_x: 10, coord_y: 0 }, [trailPoint(10, 0, 0)])).toBe(270)
  })

  it('returns null when neither a trail nor a position is available', () => {
    expect(headingFor(null)).toBeNull()
    expect(headingFor(null, [])).toBeNull()
  })
})
