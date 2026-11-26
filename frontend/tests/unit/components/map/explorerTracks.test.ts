import { describe, it, expect } from 'vite-plus/test'
import { buildExplorerTracks } from '@/modules/map/utils/explorerTracks'
import { createExploration } from '../../helpers/explorationFixtures'
import type { Exploration } from '@/modules/exploration/stores/exploration'
import type { DiscoveryRouteRead } from '@/modules/map/models/map'

function exploration(overrides: Partial<Exploration> = {}): Exploration {
  return createExploration({ id: 'expl-1', duration: 4, ...overrides })
}

const route = (
  explorationId: string,
  points: DiscoveryRouteRead['points']
): DiscoveryRouteRead => ({
  exploration_id: explorationId,
  points,
  is_active: true,
})

const point = (
  location_id: string | null,
  coord_x: number,
  coord_y: number,
  timestamp = '2026-01-01T00:00:00Z'
) => ({
  location_id,
  coord_x,
  coord_y,
  timestamp,
})

interface TrackArgs {
  routes?: DiscoveryRouteRead[]
  names?: [string, string][]
  thumbnails?: ReadonlyMap<string, string | null>
  health?: ReadonlyMap<string, number | null>
  parties?: ReadonlyMap<string, string[]>
}

/** Build tracks for one or more runs; every optional lookup map is opt-in. */
const build = (runs: Partial<Exploration> | Partial<Exploration>[], args: TrackArgs = {}) => {
  const { routes = [], names = [], thumbnails, health, parties } = args
  const list = (Array.isArray(runs) ? runs : [runs]).map((run) => exploration(run))
  return buildExplorerTracks(list, routes, new Map(names), thumbnails, health, parties)
}

describe('buildExplorerTracks', () => {
  it('maps a dispatched run to its target location id', () => {
    const tracks = build({ target_location_id: 'loc-9' })

    expect(tracks).toHaveLength(1)
    expect(tracks[0].targetLocationId).toBe('loc-9')
    expect(tracks[0].lastKnown).toBeNull()
  })

  it('uses the LAST discovery point as the free-roam last known position', () => {
    const tracks = build(
      { target_location_id: null },
      {
        routes: [
          route('expl-1', [point('loc-1', 20, 30), point('loc-2', 55, 66, '2026-01-01T01:00:00Z')]),
        ],
      }
    )

    expect(tracks[0].targetLocationId).toBeNull()
    expect(tracks[0].lastKnown).toEqual({ coord_x: 55, coord_y: 66 })
  })

  it('leaves lastKnown null when a free-roam run has no trail yet', () => {
    expect(build({}).at(0)?.lastKnown).toBeNull()
  })

  it('resolves dweller names from the provided map', () => {
    expect(build({}, { names: [['dweller-1', 'Ada Lovelace']] })[0].dwellerName).toBe(
      'Ada Lovelace'
    )
  })

  it('falls back to an empty dweller name when unknown', () => {
    expect(build({})[0].dwellerName).toBe('')
  })

  it('resolves the dweller thumbnail from the provided map', () => {
    const thumbnails = new Map([['dweller-1', 'https://cdn.example/ada.png']])

    expect(build({}, { thumbnails })[0].dwellerThumbnailUrl).toBe('https://cdn.example/ada.png')
  })

  it('leaves the dweller thumbnail null when absent or unprovided', () => {
    const withNull = build({}, { thumbnails: new Map([['dweller-1', null]]) })

    expect(withNull[0].dwellerThumbnailUrl).toBeNull()
    expect(build({})[0].dwellerThumbnailUrl).toBeNull()
  })

  it('carries the dweller id, status and vitals used by the dweller popover', () => {
    const tracks = build({ dweller_id: 'dweller-7', status: 'returning', health: 42, radiation: 7 })

    expect(tracks[0].dwellerId).toBe('dweller-7')
    expect(tracks[0].status).toBe('returning')
    expect(tracks[0].health).toBe(42)
    expect(tracks[0].radiation).toBe(7)
  })

  it('nulls vitals and keeps the active status when the run reports neither', () => {
    const track = build({})[0]

    expect(track.status).toBe('active')
    expect(track.health).toBeNull()
    expect(track.radiation).toBeNull()
  })

  it('ignores completed and recalled runs', () => {
    expect(
      build([
        { id: 'expl-1', status: 'completed' },
        { id: 'expl-2', status: 'recalled' },
      ])
    ).toHaveLength(0)
  })

  it('includes returning runs', () => {
    const tracks = build({ status: 'returning', target_location_id: 'loc-9' })

    expect(tracks).toHaveLength(1)
    expect(tracks[0].targetLocationId).toBe('loc-9')
  })

  it('resolves the dispatch party names anchor-first from the party id map', () => {
    const tracks = build(
      { target_location_id: 'loc-9' },
      {
        names: [
          ['dweller-1', 'Stephanie Boyd'],
          ['dweller-2', 'Cooper Howard'],
        ],
        parties: new Map([['expl-1', ['dweller-2', 'dweller-1', 'dweller-3']]]),
      }
    )

    expect(tracks[0].partyNames).toEqual(['Stephanie Boyd', 'Cooper Howard'])
  })

  it('collapses a dispatch to the anchor name when the party map holds only the anchor', () => {
    const tracks = build(
      {},
      {
        names: [['dweller-1', 'Ada Lovelace']],
        parties: new Map([['expl-1', ['dweller-1']]]),
      }
    )

    expect(tracks[0].partyNames).toEqual(['Ada Lovelace'])
  })

  it('falls back to the anchor name when no party data is present', () => {
    expect(build({}, { names: [['dweller-1', 'Ada Lovelace']] })[0].partyNames).toEqual([
      'Ada Lovelace',
    ])
  })

  it('drops party members whose names are not in the roster', () => {
    const tracks = build(
      {},
      {
        names: [['dweller-1', 'Ada Lovelace']],
        parties: new Map([['expl-1', ['dweller-1', 'dweller-unknown']]]),
      }
    )

    expect(tracks[0].partyNames).toEqual(['Ada Lovelace'])
  })

  it('leaves partyNames empty when no name resolves', () => {
    const tracks = build(
      { dweller_id: 'dweller-9', target_location_id: 'loc-9' },
      { parties: new Map([['expl-1', ['dweller-9', 'dweller-unknown']]]) }
    )

    expect(tracks[0].partyNames).toEqual([])
  })

  it('prefers the authoritative position over the route end', () => {
    const tracks = build(
      { pos_x: 40, pos_y: 41 },
      { routes: [route('expl-1', [point(null, 20, 30)])] }
    )

    expect(tracks[0].lastKnown?.coord_x).toBeCloseTo(64, 10)
    expect(tracks[0].lastKnown?.coord_y).toBeCloseTo(65.6, 10)
  })
})
