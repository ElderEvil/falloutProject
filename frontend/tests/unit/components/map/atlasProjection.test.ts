import { describe, expect, it } from 'vitest'
import {
  ATLAS_TILES,
  MAP_UNITS,
  UNITS_PER_TILE,
  anchorsFromPlayerVaults,
  anchorsFromVaultMarkers,
  mergeAnchors,
  registryToTile,
  registryToWire,
  wireToTile,
} from '@/modules/map/utils/atlasProjection'

describe('atlasProjection', () => {
  it('maps tiles into the 160-unit viewBox', () => {
    expect(MAP_UNITS).toBe(160)
    expect(ATLAS_TILES).toBe(80)
    expect(UNITS_PER_TILE).toBe(2)
  })

  it('converts registry → wire and wire → tile across the whole map', () => {
    expect(registryToWire(50)).toBe(80)
    // Wire coords are scaled 1.6x; the centre must stay the centre.
    expect(registryToTile(registryToWire(0))).toBe(0)
    expect(registryToTile(registryToWire(50))).toBe(40)
    expect(registryToTile(registryToWire(100))).toBe(79)
    expect(registryToTile(80)).toBe(40)
    expect(wireToTile(160)).toBe(79)
  })

  it('clamps out-of-range wire coords into the grid', () => {
    expect(registryToTile(-10)).toBe(0)
    expect(registryToTile(999)).toBe(79)
  })

  it('converts seeded vault signals to registry-space anchors', () => {
    const anchors = anchorsFromVaultMarkers([{ name: 'Vault 1', coord_x: 80, coord_y: 64 }])
    expect(anchors[0]?.coord_x).toBe(50)
    expect(anchors[0]?.coord_y).toBe(40)
    expect(anchors[0]?.terrain).toBe('wasteland')
  })

  it('converts player vault slots to registry-space anchors for preview use', () => {
    const player = anchorsFromPlayerVaults([{ vault_id: 'v1', number: 121, coord_x: 108.3, coord_y: 85.5 }])
    expect(player[0]?.id).toBe('player-vault-v1')
    expect(player[0]?.coord_x).toBeCloseTo(67.69, 1)
    const merged = mergeAnchors(
      anchorsFromVaultMarkers([{ name: 'S', coord_x: 80, coord_y: 80 }]),
      player,
      player,
    )
    expect(merged).toHaveLength(2)
  })

  it('merges seeded and player anchors without dropping either set', () => {
    // Anchor-set composition only: this does not generate terrain and does not
    // prove occupancy-independence of the rendered world. Full terrain-stability
    // coverage belongs to the backend-owned generation contract (Python lane),
    // not to this interim TS presentation path.
    const before = anchorsFromVaultMarkers([{ name: 'S', coord_x: 80, coord_y: 80 }])
    const withPlayer = mergeAnchors(
      anchorsFromVaultMarkers([{ name: 'S', coord_x: 80, coord_y: 80 }]),
      anchorsFromPlayerVaults([{ vault_id: 'v1', number: 999, coord_x: 20, coord_y: 20 }]),
    )
    expect(before).toHaveLength(1)
    expect(withPlayer).toHaveLength(2)
  })
})
