import { bearingDegrees } from './bearing'
import type { DiscoveryRouteRead, ExplorerTrack } from '../models/map'

type Coord = { coord_x: number; coord_y: number }

/**
 * Direction of travel for a free-roam explorer marker, in compass degrees
 * (0 = N, 90 = E; see bearingDegrees for the coordinate convention).
 *
 * Priority:
 *  1. The vector between the last two trail points — where the run has been
 *     heading on its outbound leg.
 *  2. With no usable trail, aim from the last known position toward home: a
 *     free-roam runner with a position but no outbound trail is coming back.
 *     (Returning runs do not extend the trail, so it cannot speak for them.)
 *  3. Otherwise no heading is derivable — the marker renders without a chevron.
 */
export function explorerHeading(
  track: Pick<ExplorerTrack, 'lastKnown'>,
  route: Pick<DiscoveryRouteRead, 'points'> | undefined,
  home: Coord
): number | null {
  const points = route?.points ?? []
  if (points.length >= 2) {
    const from = points[points.length - 2]
    const to = points[points.length - 1]
    return bearingDegrees({ x: from.coord_x, y: from.coord_y }, { x: to.coord_x, y: to.coord_y })
  }
  if (track.lastKnown) {
    return bearingDegrees(
      { x: track.lastKnown.coord_x, y: track.lastKnown.coord_y },
      { x: home.coord_x, y: home.coord_y }
    )
  }
  return null
}
