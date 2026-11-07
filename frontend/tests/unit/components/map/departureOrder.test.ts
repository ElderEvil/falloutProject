import { describe, expect, it } from 'vite-plus/test'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import { sortDepartureCandidates } from '@/modules/map/utils/departureOrder'

const roomNameById = new Map([
  ['room-power', 'Power Plant'],
  ['room-diner', 'Diner'],
])

function createDweller(id: string, roomId: string | null, first_name: string): DwellerShort {
  return {
    id,
    first_name,
    last_name: null,
    status: roomId ? 'working' : 'idle',
    room_id: roomId,
  } as DwellerShort
}

describe('sortDepartureCandidates', () => {
  it('keeps idle dwellers first, then groups employed dwellers by job name', () => {
    const candidates = [
      createDweller('diner-1', 'room-diner', 'Dana'),
      createDweller('idle-1', null, 'Bea'),
      createDweller('power-1', 'room-power', 'Cal'),
      createDweller('idle-2', null, 'Abe'),
      createDweller('diner-2', 'room-diner', 'Eve'),
    ]

    const sorted = sortDepartureCandidates(candidates, roomNameById)

    expect(sorted.map((dweller) => dweller.id)).toEqual([
      'idle-1',
      'idle-2',
      'diner-1',
      'diner-2',
      'power-1',
    ])
  })

  it('does not mutate the caller-owned list', () => {
    const candidates = [
      createDweller('diner-1', 'room-diner', 'Dana'),
      createDweller('idle-1', null, 'Bea'),
    ]

    sortDepartureCandidates(candidates, roomNameById)

    expect(candidates.map((dweller) => dweller.id)).toEqual(['diner-1', 'idle-1'])
  })
})
