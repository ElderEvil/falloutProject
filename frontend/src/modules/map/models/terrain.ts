// Snapshot terrain vocabulary shared by the map renderer and projection.
// The backend owns this vocabulary (world_generation_service.TERRAIN_KINDS);
// the frontend only renders persisted snapshots verbatim, never generates.

export type TerrainType = 'wasteland' | 'forest' | 'ruins' | 'hills' | 'water'

export interface TerrainAnchor {
  id: string
  name: string
  coord_x: number
  coord_y: number
  terrain: Exclude<TerrainType, 'water'>
}
