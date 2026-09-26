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
      const lastPoint = routesByExploration.get(exploration.id)?.points.at(-1)
      return {
        explorationId: exploration.id,
        dwellerName: dwellerNames.get(exploration.dweller_id) ?? '',
        targetLocationId: exploration.target_location_id ?? null,
        lastKnown: lastPoint
          ? { coord_x: lastPoint.coord_x, coord_y: lastPoint.coord_y }
          : null,
      }
    })
}
