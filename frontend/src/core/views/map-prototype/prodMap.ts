import apiClient from '@/core/plugins/axios'
import type { components } from '@/core/types/api.generated'

export type ProdMapResponse = components['schemas']['VaultMapResponse']
export type ProdLocation = components['schemas']['WastelandLocationWithDwellers']

export interface PublicAnchor {
  name: string
  coord_x: number
  coord_y: number
}

export function registryToCanvas(coord: number, canvasSize = 640): number {
  return (coord * canvasSize) / 100
}

/** Nearest projected tile center, clamped to the grid; never rewrites marker coordinates. */
export function registryToTile(coord: number, tiles = 80): number {
  const t = Math.round((coord / 100) * tiles - 0.5)
  return Math.min(tiles - 1, Math.max(0, t))
}

export function filterUnlocked(locations: ProdLocation[]): ProdLocation[] {
  return locations.filter(l => l.is_unlocked === true)
}

export async function fetchProdMap(
  vaultId: string,
): Promise<{ unlocked: ProdLocation[]; total: number; anchors: PublicAnchor[] }> {
  const response = await apiClient.get<ProdMapResponse>(
    `/api/v1/map/vault/${vaultId}`,
    { params: { unlocked_only: true }, _skipErrorNotification: true },
  )
  const locations = response.data.locations ?? []
  // Seeded vault rows are global (kind=VAULT, source=seed), returned regardless of
  // unlock state. Wire coordinates are scaled/rounded; retain the read-only signals,
  // but do not treat them as verified exact terrain anchors.
  const anchors = (response.data.vault_markers ?? []).map(marker => ({
    name: marker.name,
    coord_x: marker.coord_x,
    coord_y: marker.coord_y,
  }))
  return { unlocked: filterUnlocked(locations), total: locations.length, anchors }
}
