/**
 * Deterministic, framework-free marker clustering for the world map.
 *
 * Points are bucketed into a uniform grid whose cell size shrinks as the map
 * zooms in (`cellSize / zoom`). At overview zoom nearby points share a cell and
 * merge into a single cluster; zooming in shrinks the cells until every point
 * is its own cluster again. Unlike a random/iterative approach the output is
 * fully deterministic — same input always yields the same clusters — so the
 * rendered badges are stable across re-renders and polling.
 *
 * Coordinates remain authoritative; badges render at their members' centroid.
 */

export interface ClusterPoint {
  id: string
  x: number
  y: number
}

export interface MarkerCluster {
  id: string
  /** Centroid of the member points. */
  x: number
  y: number
  /** Members, sorted by id so the cluster shape is order-independent. */
  members: ClusterPoint[]
}

export interface ClusterOptions {
  /** Grid cell size in map units at zoom 1. Default 16. */
  cellSize?: number
  /** Group touching points by distance instead of grid cells (map units at zoom 1). */
  distance?: number
  /** Current map zoom (>= 1). Effective cell size is cellSize / zoom. Default 1. */
  zoom?: number
}

export const DEFAULT_CLUSTER_CELL_SIZE = 16

function compareIds(a: string, b: string): number {
  if (a < b) return -1
  if (a > b) return 1
  return 0
}

/**
 * Group points by zoom-scaled grid cells, or touching distance when requested.
 *
 * Returns clusters in a stable order. A group with a
 * single point comes back as a singleton cluster at the point's exact
 * position, so callers can render it through the normal marker path.
 */
export function clusterMarkers(
  points: ClusterPoint[],
  options: ClusterOptions = {}
): MarkerCluster[] {
  const cellSize =
    (options.cellSize ?? DEFAULT_CLUSTER_CELL_SIZE) / Math.max(options.zoom ?? 1, 0.01)

  const buckets = new Map<string, ClusterPoint[]>()
  const distance =
    options.distance === undefined ? null : options.distance / Math.max(options.zoom ?? 1, 0.01)
  for (const point of [...points].sort((a, b) => compareIds(a.id, b.id))) {
    if (distance !== null) {
      const touching = [...buckets.entries()].filter(([, members]) =>
        members.some((member) => Math.hypot(member.x - point.x, member.y - point.y) <= distance)
      )
      const key = touching[0]?.[0] ?? point.id
      for (const [id] of touching) buckets.delete(id)
      buckets.set(key, [point, ...touching.flatMap(([, members]) => members)])
      continue
    }
    const cellX = Math.floor(point.x / cellSize)
    const cellY = Math.floor(point.y / cellSize)
    const key = `${cellX}:${cellY}`
    const bucket = buckets.get(key)
    if (bucket) bucket.push(point)
    else buckets.set(key, [point])
  }

  return [...buckets.entries()]
    .map(([key, members]) => {
      const sorted = [...members].sort((a, b) => compareIds(a.id, b.id))
      let sumX = 0
      let sumY = 0
      for (const member of sorted) {
        sumX += member.x
        sumY += member.y
      }
      return {
        id: `cluster-${key}`,
        x: sumX / sorted.length,
        y: sumY / sorted.length,
        members: sorted,
      }
    })
    .sort((a, b) => compareIds(a.id, b.id))
}
