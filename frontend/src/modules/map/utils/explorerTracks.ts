import type { Exploration } from '@/modules/exploration/stores/exploration'
import type { DiscoveryRouteRead, ExplorerTrack } from '../models/map'
import { registryToWire } from './atlasProjection'

/** Discovery routes indexed by exploration id — shared by track building and the map's free-roam headings. */
export function buildRoutesByExploration(
  discoveryRoutes: DiscoveryRouteRead[]
): Map<string, DiscoveryRouteRead> {
  return new Map(discoveryRoutes.map((route) => [route.exploration_id, route]))
}

export function buildExplorerTracks(
  explorations: Exploration[],
  discoveryRoutes: DiscoveryRouteRead[],
  dwellerNames: ReadonlyMap<string, string>,
  dwellerThumbnails: ReadonlyMap<string, string | null> = new Map(),
  dwellerMaxHealth: ReadonlyMap<string, number | null> = new Map()
): ExplorerTrack[] {
  const routesByExploration = buildRoutesByExploration(discoveryRoutes)
  return explorations
    .filter(
      (e): e is Exploration & { status: 'active' | 'returning' } =>
        e.status === 'active' || e.status === 'returning'
    )
    .map((exploration) => {
      // Prefer the authoritative current position: return movement updates
      // pos without extending the trail, so the route end would strand the
      // marker at the outbound endpoint. Store positions are registry units;
      // the map renders wire units, like every other backend coordinate.
      const lastPoint = routesByExploration.get(exploration.id)?.points.at(-1)
      const position =
        exploration.pos_x != null && exploration.pos_y != null
          ? {
              coord_x: registryToWire(exploration.pos_x),
              coord_y: registryToWire(exploration.pos_y),
            }
          : lastPoint
            ? { coord_x: lastPoint.coord_x, coord_y: lastPoint.coord_y }
            : null
      return {
        explorationId: exploration.id,
        dwellerId: exploration.dweller_id,
        dwellerName: dwellerNames.get(exploration.dweller_id) ?? '',
        status: exploration.status,
        health: exploration.health ?? null,
        radiation: exploration.radiation ?? null,
        maxHealth: dwellerMaxHealth.get(exploration.dweller_id) ?? null,
        targetLocationId: exploration.target_location_id ?? null,
        lastKnown: position,
        dwellerThumbnailUrl: dwellerThumbnails.get(exploration.dweller_id) ?? null,
      }
    })
}
