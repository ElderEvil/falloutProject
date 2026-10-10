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
  return { exploration_id: explorationId, points, is_active: true }
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

  it('resolves the dweller thumbnail from the provided map', () => {
    const tracks = buildExplorerTracks(
      [exploration({ id: 'expl-1', dweller_id: 'dweller-1' })],
      [],
      new Map(),
      new Map([['dweller-1', 'https://cdn.example/ada.png']])
    )

    expect(tracks[0].dwellerThumbnailUrl).toBe('https://cdn.example/ada.png')
  })

  it('leaves the dweller thumbnail null when absent or unprovided', () => {
    const withNull = buildExplorerTracks(
      [exploration({ id: 'expl-1', dweller_id: 'dweller-1' })],
      [],
      new Map(),
      new Map([['dweller-1', null]])
    )
    const withoutMap = buildExplorerTracks(
      [exploration({ id: 'expl-1', dweller_id: 'dweller-1' })],
      [],
      new Map()
    )

    expect(withNull[0].dwellerThumbnailUrl).toBeNull()
    expect(withoutMap[0].dwellerThumbnailUrl).toBeNull()
  })

  it('carries the dweller id, status and vitals used by the dweller popover', () => {
    const tracks = buildExplorerTracks(
      [
        exploration({
          id: 'expl-1',
          dweller_id: 'dweller-7',
          status: 'returning',
          health: 42,
          radiation: 7,
        }),
      ],
      [],
      new Map()
    )

    expect(tracks[0].dwellerId).toBe('dweller-7')
    expect(tracks[0].status).toBe('returning')
    expect(tracks[0].health).toBe(42)
    expect(tracks[0].radiation).toBe(7)
  })

  it('nulls vitals and keeps the active status when the run reports neither', () => {
    const tracks = buildExplorerTracks([exploration({ id: 'expl-1' })], [], new Map())

    expect(tracks[0].status).toBe('active')
    expect(tracks[0].health).toBeNull()
    expect(tracks[0].radiation).toBeNull()
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

  it('resolves the dispatch party names anchor-first from the party id map', () => {
    const tracks = buildExplorerTracks(
      [exploration({ id: 'expl-1', dweller_id: 'dweller-1', target_location_id: 'loc-9' })],
      [],
      new Map([
        ['dweller-1', 'Stephanie Boyd'],
        ['dweller-2', 'Cooper Howard'],
      ]),
      new Map(),
      new Map(),
      new Map([['expl-1', ['dweller-2', 'dweller-1', 'dweller-3']]])
    )

    expect(tracks[0].partyNames).toEqual(['Stephanie Boyd', 'Cooper Howard'])
  })

  it('collapses a dispatch to the anchor name when the party map holds only the anchor', () => {
    const tracks = buildExplorerTracks(
      [exploration({ id: 'expl-1', dweller_id: 'dweller-1' })],
      [],
      new Map([['dweller-1', 'Ada Lovelace']]),
      new Map(),
      new Map(),
      new Map([['expl-1', ['dweller-1']]])
    )

    expect(tracks[0].partyNames).toEqual(['Ada Lovelace'])
  })

  it('falls back to the anchor name when no party data is present', () => {
    const tracks = buildExplorerTracks(
      [exploration({ id: 'expl-1', dweller_id: 'dweller-1' })],
      [],
      new Map([['dweller-1', 'Ada Lovelace']])
    )

    expect(tracks[0].partyNames).toEqual(['Ada Lovelace'])
  })

  it('drops party members whose names are not in the roster', () => {
    const tracks = buildExplorerTracks(
      [exploration({ id: 'expl-1', dweller_id: 'dweller-1' })],
      [],
      new Map([['dweller-1', 'Ada Lovelace']]),
      new Map(),
      new Map(),
      new Map([['expl-1', ['dweller-1', 'dweller-unknown']]])
    )

    expect(tracks[0].partyNames).toEqual(['Ada Lovelace'])
  })

  it('leaves partyNames empty when no name resolves', () => {
    const tracks = buildExplorerTracks(
      [exploration({ id: 'expl-1', dweller_id: 'dweller-9', target_location_id: 'loc-9' })],
      [],
      new Map(),
      new Map(),
      new Map(),
      new Map([['expl-1', ['dweller-9', 'dweller-unknown']]])
    )

    expect(tracks[0].partyNames).toEqual([])
  })

  it('prefers the authoritative position over the route end', () => {
    const tracks = buildExplorerTracks(
      [exploration({ id: 'expl-1', pos_x: 40, pos_y: 41 })],
      [
        route('expl-1', [
          { location_id: null, coord_x: 20, coord_y: 30, timestamp: '2026-01-01T00:00:00Z' },
        ]),
      ],
      new Map()
    )

    expect(tracks[0].lastKnown?.coord_x).toBeCloseTo(64, 10)
    expect(tracks[0].lastKnown?.coord_y).toBeCloseTo(65.6, 10)
  })
})
