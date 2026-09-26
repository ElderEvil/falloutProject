import { describe, it, expect } from 'vitest'
import { buildExplorerTracks } from '@/modules/map/utils/explorerTracks'
import type { Exploration } from '@/modules/exploration/stores/exploration'
import type { DiscoveryRouteRead } from '@/modules/map/models/map'

function exploration(overrides: Partial<Exploration> = {}): Exploration {
  return {
    id: 'expl-1',
    vault_id: 'vault-1',
    dweller_id: 'dweller-1',
    status: 'active',
    duration: 4,
    start_time: '2026-01-01T00:00:00Z',
    end_time: null,
    events: [],
    loot_collected: [],
    total_distance: 0,
    total_caps_found: 0,
    enemies_encountered: 0,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    dweller_strength: 1,
    dweller_perception: 1,
    dweller_endurance: 1,
    dweller_charisma: 1,
    dweller_intelligence: 1,
    dweller_agility: 1,
    dweller_luck: 1,
    stimpaks: 0,
    radaways: 0,
    ...overrides,
  }
}

function route(explorationId: string, points: DiscoveryRouteRead['points']): DiscoveryRouteRead {
  return { exploration_id: explorationId, points }
}

describe('buildExplorerTracks', () => {
  it('maps a dispatched run to its target location id', () => {
    const tracks = buildExplorerTracks(
      [exploration({ id: 'expl-1', target_location_id: 'loc-9' })],
      [],
      new Map()
    )

    expect(tracks).toHaveLength(1)
    expect(tracks[0].targetLocationId).toBe('loc-9')
    expect(tracks[0].lastKnown).toBeNull()
  })

  it('uses the LAST discovery point as the free-roam last known position', () => {
    const tracks = buildExplorerTracks(
      [exploration({ id: 'expl-1', target_location_id: null })],
      [
        route('expl-1', [
          { location_id: 'loc-1', coord_x: 20, coord_y: 30, timestamp: '2026-01-01T00:00:00Z' },
          { location_id: 'loc-2', coord_x: 55, coord_y: 66, timestamp: '2026-01-01T01:00:00Z' },
        ]),
      ],
      new Map()
    )

    expect(tracks[0].targetLocationId).toBeNull()
    expect(tracks[0].lastKnown).toEqual({ coord_x: 55, coord_y: 66 })
  })

  it('leaves lastKnown null when a free-roam run has no trail yet', () => {
    const tracks = buildExplorerTracks([exploration({ id: 'expl-1' })], [], new Map())

    expect(tracks[0].lastKnown).toBeNull()
  })

  it('resolves dweller names from the provided map', () => {
    const tracks = buildExplorerTracks(
      [exploration({ id: 'expl-1', dweller_id: 'dweller-1' })],
      [],
      new Map([['dweller-1', 'Ada Lovelace']])
    )

    expect(tracks[0].dwellerName).toBe('Ada Lovelace')
  })

  it('falls back to an empty dweller name when unknown', () => {
    const tracks = buildExplorerTracks([exploration({ id: 'expl-1' })], [], new Map())

    expect(tracks[0].dwellerName).toBe('')
  })

  it('ignores completed and recalled runs', () => {
    const tracks = buildExplorerTracks(
      [
        exploration({ id: 'expl-1', status: 'completed' }),
        exploration({ id: 'expl-2', status: 'recalled' }),
      ],
      [],
      new Map()
    )

    expect(tracks).toHaveLength(0)
  })

  it('includes returning runs', () => {
    const tracks = buildExplorerTracks(
      [exploration({ id: 'expl-1', status: 'returning', target_location_id: 'loc-9' })],
      [],
      new Map()
    )

    expect(tracks).toHaveLength(1)
    expect(tracks[0].targetLocationId).toBe('loc-9')
  })
})
