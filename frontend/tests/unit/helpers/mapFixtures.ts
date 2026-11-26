import type {
  ExpeditionSiteMarkerRead,
  VaultMarkerRead,
  WastelandLocationWithDwellers,
} from '@/modules/map/models/map'

/** Location fixture shared by the map-domain suites. */
export function createLocation(
  overrides: Partial<WastelandLocationWithDwellers> = {}
): WastelandLocationWithDwellers {
  return {
    id: 'loc-1',
    name: 'Rusty Depot',
    normalized_name: 'rusty depot',
    type: 'origin',
    coord_x: 50,
    coord_y: 50,
    description: null,
    vault_id: 'vault-1',
    exploration_id: null,
    created_at: null,
    dwellers: [],
    ...overrides,
  }
}

export function createVaultMarker(overrides: Partial<VaultMarkerRead> = {}): VaultMarkerRead {
  return {
    name: 'Vault 88',
    coord_x: 30,
    coord_y: 40,
    type: 'vault',
    description: 'Unexplored vault signal',
    ...overrides,
  }
}

export function createSite(
  overrides: Partial<ExpeditionSiteMarkerRead> = {}
): ExpeditionSiteMarkerRead {
  return {
    id: 'site-1',
    name: 'Red Rocket Gas Station',
    flavor: 'A roadside fuel stop.',
    coord_x: 60,
    coord_y: 70,
    min_dweller_level: 5,
    room_total: 3,
    cleared: false,
    cooldown_remaining_seconds: 0,
    block_reason: null,
    ...overrides,
  }
}
