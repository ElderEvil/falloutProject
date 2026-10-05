import type { Exploration } from '@/modules/exploration/stores/exploration'
import type { DiscoveryRouteRead, ExplorerTrack } from '../models/map'

export function buildExplorerTracks(
  explorations: Exploration[],
  discoveryRoutes: DiscoveryRouteRead[],
  dwellerNames: ReadonlyMap<string, string>
): ExplorerTrack[] {
  const routesByExploration = new Map(discoveryRoutes.map((route) => [route.exploration_id, route]))
  return explorations
    .filter((e) => e.status === 'active' || e.status === 'returning')
    .map((exploration) => {
      // Prefer the authoritative current position: return movement updates
      // pos without extending the trail, so the route end would strand the
      // marker at the outbound endpoint. The trail stays traveled coverage.
      const lastPoint = routesByExploration.get(exploration.id)?.points.at(-1)
      const position =
        exploration.pos_x != null && exploration.pos_y != null
          ? { coord_x: exploration.pos_x, coord_y: exploration.pos_y }
          : lastPoint
            ? { coord_x: lastPoint.coord_x, coord_y: lastPoint.coord_y }
            : null
      return {
        explorationId: exploration.id,
        dwellerName: dwellerNames.get(exploration.dweller_id) ?? '',
        targetLocationId: exploration.target_location_id ?? null,
        lastKnown: position,
      }
    })
}
