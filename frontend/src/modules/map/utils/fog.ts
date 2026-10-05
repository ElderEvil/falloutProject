import { ATLAS_TILES, registryToTile } from './atlasProjection'

/** Reveal radii (in atlas tiles) for the derived explored mask. */
export const HOME_REVEAL = 8
export const SITE_REVEAL = 7
export const TRAIL_REVEAL = 4

export interface FogPoint {
  coord_x: number
  coord_y: number
}

export interface FogInput {
  home?: FogPoint | null
  discovered: ReadonlyArray<FogPoint>
  trailPoints: ReadonlyArray<FogPoint>
  /** Movement trails (dense breadcrumbs); segments between consecutive points reveal too. */
  travelRoutes?: ReadonlyArray<ReadonlyArray<FogPoint>>
}

function reveal(mask: Uint8Array, tiles: number, cx: number, cy: number, radius: number): void {
  for (let dy = -radius; dy <= radius; dy++) {
    for (let dx = -radius; dx <= radius; dx++) {
      if (dx * dx + dy * dy > radius * radius) continue
      const x = cx + dx
      const y = cy + dy
      if (x < 0 || x >= tiles || y < 0 || y >= tiles) continue
      mask[y * tiles + x] = 1
    }
  }
}

/**
 * Fog of war, derived from authoritative discovery state — no new persistence.
 * A tile is explored when it lies within reveal range of the home vault, a
 * discovered location, or a discovery-trail point. Movement trails additionally
 * reveal the segments between consecutive points, so a long catch-up advance
 * cannot leave an unexplored midpoint between two revealed endpoints.
 * This is a presentation aid, not an authorization boundary.
 */
export function computeExploredMask(input: FogInput, tiles = ATLAS_TILES): Uint8Array {
  const mask = new Uint8Array(tiles * tiles)
  const revealAt = (point: FogPoint, radius: number): void =>
    reveal(mask, tiles, registryToTile(point.coord_x, tiles), registryToTile(point.coord_y, tiles), radius)
  const revealSegment = (from: FogPoint, to: FogPoint, radius: number): void => {
    const ax = registryToTile(from.coord_x, tiles)
    const ay = registryToTile(from.coord_y, tiles)
    const bx = registryToTile(to.coord_x, tiles)
    const by = registryToTile(to.coord_y, tiles)
    const steps = Math.max(1, Math.ceil(Math.hypot(bx - ax, by - ay)))
    for (let i = 0; i <= steps; i++) {
      reveal(
        mask,
        tiles,
        Math.round(ax + ((bx - ax) * i) / steps),
        Math.round(ay + ((by - ay) * i) / steps),
        radius,
      )
    }
  }

  if (input.home) revealAt(input.home, HOME_REVEAL)
  for (const location of input.discovered) revealAt(location, SITE_REVEAL)
  for (const point of input.trailPoints) revealAt(point, TRAIL_REVEAL)
  for (const route of input.travelRoutes ?? [])
    for (let i = 1; i < route.length; i++) revealSegment(route[i - 1], route[i], TRAIL_REVEAL)
  return mask
}

export function isExploredTile(mask: Uint8Array, x: number, y: number, tiles = ATLAS_TILES): boolean {
  if (x < 0 || x >= tiles || y < 0 || y >= tiles) return false
  return mask[y * tiles + x] === 1
}
