import source from './worldSnapshot.json'
import type { TerrainType } from '../models/terrain'
import type {
  DiscoveryRouteRead,
  ExpeditionSiteMarkerRead,
  PlaceGroup,
  WastelandLocationWithDwellers,
  WorldSnapshotRead,
} from '../models/map'

// Exported from generate_world(WorldRecipe(seed='wasteland-atlas-v1')).
// Compact cell codes are fixture data, not a second world generator.
const terrainCodes: Record<string, TerrainType> = {
  w: 'wasteland',
  f: 'forest',
  r: 'ruins',
  h: 'hills',
  a: 'water',
}
export const previewSnapshot: WorldSnapshotRead = {
  world_id: source.world_id,
  generator_version: source.generator_version,
  recipe_fingerprint: source.recipe_fingerprint,
  snapshot_checksum: source.snapshot_checksum,
  width: source.width,
  height: source.height,
  slots: source.slots,
  terrain: source.rows.flatMap((row) => row.split('').map((code) => terrainCodes[code]!)),
}

function land(x: number, y: number): { coord_x: number; coord_y: number } {
  const tile = previewSnapshot.terrain.reduce(
    (nearest, terrain, index) => {
      if (terrain === 'water') return nearest
      const distance = Math.hypot(
        (index % source.width) * 2 + 1 - x,
        Math.floor(index / source.width) * 2 + 1 - y
      )
      return distance < nearest.distance ? { index, distance } : nearest
    },
    { index: 0, distance: Infinity }
  ).index
  return {
    coord_x: (tile % source.width) * 2 + 1,
    coord_y: Math.floor(tile / source.width) * 2 + 1,
  }
}

function location(
  id: string,
  name: string,
  x: number,
  y: number,
  group: string,
  unlocked = true
): WastelandLocationWithDwellers {
  return {
    id,
    name,
    normalized_name: name.toLowerCase(),
    ...land(x, y),
    type: id === 'home' ? 'home_vault' : 'discovery',
    description: 'A place recorded in the regional survey.',
    group_key: group,
    vault_id: 'preview-vault',
    exploration_id: null,
    created_at: '2026-10-26T12:00:00',
    dwellers: [],
    is_unlocked: unlocked,
  }
}

export const previewLocations = [
  location('home', 'Vault 101', 35, 92, 'settlement'),
  location('rocket', 'Red Rocket', 61, 70, 'gas_station'),
  location('relay', 'Relay Station', 85, 38, 'radio'),
  location('factory', 'Old Foundry', 115, 104, 'industrial'),
  location('market', 'Super Duper Mart', 112, 55, 'supermarket'),
  location('camp', 'Ranger Camp', 48, 40, 'settlement'),
  location('unknown', 'Unidentified Signal', 81, 109, 'industrial', false),
]

export const denseLocations = Array.from({ length: 9 }, (_, i) =>
  location(
    `cluster-${i}`,
    `Survey Point ${i + 1}`,
    62 + (i % 3) * 3,
    72 + Math.floor(i / 3) * 3,
    'settlement'
  )
)

export const previewGroups: PlaceGroup[] = [
  ['settlement', 'Settlement', 'mdi:home-group'],
  ['gas_station', 'Gas station', 'mdi:gas-station'],
  ['radio', 'Relay', 'mdi:radio-tower'],
  ['industrial', 'Industrial', 'mdi:factory'],
  ['supermarket', 'Supermarket', 'mdi:cart'],
].map(([key, label, icon]) => ({
  key: key!,
  label: label!,
  icon: icon!,
  risk: 'low',
  description: label!,
  clearable: false,
}))

export const previewSites: ExpeditionSiteMarkerRead[] = [
  {
    id: 'collapsed_subway',
    name: 'Collapsed Subway',
    flavor: 'Movement beneath the broken platforms.',
    ...land(50, 120),
    min_dweller_level: 1,
    room_total: 1,
    cleared: false,
    cooldown_remaining_seconds: 0,
    exploration_id: 'preview-exploration',
  },
]

export const previewRoutes: DiscoveryRouteRead[] = [
  {
    exploration_id: 'preview-exploration',
    is_active: true,
    points: [previewLocations[0]!, previewLocations[1]!, previewLocations[4]!].map((point) => ({
      coord_x: point.coord_x,
      coord_y: point.coord_y,
      timestamp: '2026-10-26T12:00:00',
    })),
  },
]

// Small cartographic marks stay within their actual snapshot cells.
export const terrainRelief: Record<TerrainType, string> = {
  wasteland: '',
  forest: '',
  ruins: '',
  hills: '',
  water: '',
}
previewSnapshot.terrain.forEach((terrain, index) => {
  const col = index % source.width
  const row = Math.floor(index / source.width)
  if (col % 3 || row % 3) return
  const x = col * 2 + 1
  const y = row * 2 + 1
  const marks: Record<TerrainType, string> = {
    forest: `M${x} ${y - 1.3}l-1 1.7h.5l-.8 1h2.6l-.8-1h.5Z`,
    hills: `M${x - 1.5} ${y + 0.4}q1.5-2 3 0m-2.5.7q1-1.2 2 0`,
    ruins: `M${x - 0.8} ${y}h.5m.5-.5h.7m-.4 1.2h.4`,
    water: `M${x - 1.4} ${y}q.7-.5 1.4 0t1.4 0`,
    wasteland: `M${x} ${y}h.35`,
  }
  terrainRelief[terrain as TerrainType] += marks[terrain as TerrainType]
})
