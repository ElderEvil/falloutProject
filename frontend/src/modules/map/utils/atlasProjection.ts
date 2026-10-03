import type { TerrainAnchor, TerrainType } from './atlasWorldgen'

/** SVG viewBox size of the production map. */
export const MAP_UNITS = 160
/** Tile grid size of the generated atlas world. */
export const ATLAS_TILES = 80
/** Fixed world seed: one shared geography for every vault. */
export const ATLAS_SEED = 'wasteland-atlas-v1'
/** SVG units per tile. */
export const UNITS_PER_TILE = MAP_UNITS / ATLAS_TILES

/**
 * Single source of truth for atlas biome colours. Values live as `@theme` tokens
 * in `assets/tailwind.css`; this maps each biome to its token so the terrain
 * render and the legend stay in sync and themes can retint them.
 */
export const ATLAS_TERRAIN_VAR: Record<TerrainType, string> = {
  wasteland: '--color-terrain-wasteland',
  forest: '--color-terrain-forest',
  ruins: '--color-terrain-ruins',
  hills: '--color-terrain-hills',
  water: '--color-terrain-water',
}

/** Tailwind utility classes for the same tokens (legend swatches). */
export const ATLAS_TERRAIN_CLASS: Record<TerrainType, string> = {
  wasteland: 'bg-terrain-wasteland',
  forest: 'bg-terrain-forest',
  ruins: 'bg-terrain-ruins',
  hills: 'bg-terrain-hills',
  water: 'bg-terrain-water',
}

export const ATLAS_TERRAIN_ORDER: readonly TerrainType[] = [
  'wasteland',
  'forest',
  'ruins',
  'hills',
  'water',
]

export const ATLAS_TERRAIN_LABEL: Record<TerrainType, string> = {
  wasteland: 'Wasteland',
  forest: 'Forest',
  ruins: 'Ruins',
  hills: 'Hills',
  water: 'Water',
}

/** Scale the backend applies to registry coordinates on the wire (0-100 → 0-160). */
export const WIRE_SCALE = 1.6

/** Registry coordinate (0-100) → wire/SVG coordinate (0-160). */
export function registryToWire(coord: number): number {
  return coord * WIRE_SCALE
}

/** Wire/SVG coordinate (0-160) → atlas tile (0..tiles). */
export function wireToTile(coord: number, tiles = ATLAS_TILES): number {
  const tile = Math.round((coord / WIRE_SCALE / 100) * tiles - 0.5)
  return Math.min(tiles - 1, Math.max(0, tile))
}

/** Wire/SVG coordinate (0-160) → registry coordinate (0-100). */
export function wireToRegistry(coord: number): number {
  return coord / WIRE_SCALE
}

/**
 * Wire coordinate (0-160) → atlas tile, the documented tile-center inverse.
 * Map wire coordinates are already scaled; never feed raw registry coords here.
 */
export function registryToTile(coord: number, tiles = ATLAS_TILES): number {
  return wireToTile(coord, tiles)
}

/**
 * Shared public anchors for the atlas world, from map wire coordinates. They are
 * global (not per-vault), so geography stays shared; the API returns them
 * scaled/rounded, so this is an anchoring input, not exact registry coordinates.
 */
export function anchorsFromVaultMarkers(
  markers: ReadonlyArray<{ name: string; coord_x: number; coord_y: number }>,
): TerrainAnchor[] {
  return markers.map((marker, i) => ({
    id: `seed-vault-${i}`,
    name: marker.name,
    coord_x: wireToRegistry(marker.coord_x),
    coord_y: wireToRegistry(marker.coord_y),
    terrain: 'wasteland',
  }))
}

/**
 * Anchors from real player vault slots (wire coords), so a vault always sits on
 * passable land. Global placements, so geography stays shared across vaults.
 */
export function anchorsFromPlayerVaults(
  vaults: ReadonlyArray<{ vault_id: string; number: number; coord_x: number; coord_y: number }>,
): TerrainAnchor[] {
  return vaults.map(vault => ({
    id: `player-vault-${vault.vault_id}`,
    name: `Vault ${vault.number}`,
    coord_x: wireToRegistry(vault.coord_x),
    coord_y: wireToRegistry(vault.coord_y),
    terrain: 'wasteland',
  }))
}

/** Merge anchor sets, dropping duplicate ids so a world can be generated once. */
export function mergeAnchors(...groups: TerrainAnchor[][]): TerrainAnchor[] {
  const byId = new Map<string, TerrainAnchor>()
  for (const group of groups) {
    for (const anchor of group) byId.set(anchor.id, anchor)
  }
  return [...byId.values()]
}
