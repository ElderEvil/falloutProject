import type { components } from '@/core/types/api.generated'

// Type aliases from generated OpenAPI schemas
export type WastelandLocationWithDwellers = components['schemas']['WastelandLocationWithDwellers']
export type VaultMarkerRead = components['schemas']['VaultMarkerRead']
export type PlayerVaultMarkerRead = components['schemas']['PlayerVaultMarkerRead']
export type DiscoveryRouteRead = components['schemas']['DiscoveryRouteRead']
export type VaultMapResponse = components['schemas']['VaultMapResponse']
export type DwellerRef = components['schemas']['DwellerRef']
export type PlaceGroup = components['schemas']['PlaceGroupRead']
export type ExpeditionSiteMarkerRead = components['schemas']['ExpeditionSiteMarkerRead']
export type WorldSlotRead = components['schemas']['WorldSlotRead']
export type WorldSnapshotRead = components['schemas']['WorldSnapshotRead']

export interface ExplorerTrack {
  explorationId: string
  /**
   * Dweller popover fields. Optional so the frozen `/dev/map-mockup` fixture
   * (`MOCK_EXPLORER_TRACKS`, which predates them) still typechecks;
   * `buildExplorerTracks` always populates every one of them.
   */
  dwellerId?: string
  status?: 'active' | 'returning'
  health?: number | null
  radiation?: number | null
  dwellerName: string
  targetLocationId: string | null
  lastKnown: { coord_x: number; coord_y: number } | null
  dwellerThumbnailUrl?: string | null
}

export type MarkerClickPayload =
  | { kind: 'location'; data: WastelandLocationWithDwellers }
  | { kind: 'vault'; data: VaultMarkerRead }
  | { kind: 'site'; data: ExpeditionSiteMarkerRead }
