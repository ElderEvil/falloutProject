import { describe, expect, it } from 'vite-plus/test'
import {
  getRoomSegmentCount,
  getTrainingRoomCapacity,
  isRoomAtRowEnd,
  getMergeCandidates,
} from '@/modules/rooms/utils/room'
import type { Room } from '@/modules/rooms/models/room'

const room = (overrides: Partial<Room> = {}): Pick<Room, 'size' | 'size_min'> => ({
  size: 3,
  size_min: 3,
  ...overrides,
})

describe('getRoomSegmentCount', () => {
  it('counts a plain room as a single segment', () => {
    expect(getRoomSegmentCount(room())).toBe(1)
  })

  it('counts every segment of a merged room', () => {
    expect(getRoomSegmentCount(room({ size: 6 }))).toBe(2)
    expect(getRoomSegmentCount(room({ size: 9 }))).toBe(3)
  })

  it('treats fixed-size rooms as one segment', () => {
    expect(getRoomSegmentCount(room({ size: 6, size_min: 6 }))).toBe(1)
  })

  it('falls back to size_min when size is missing', () => {
    expect(getRoomSegmentCount({ size: null, size_min: 3 })).toBe(1)
  })
})

describe('getTrainingRoomCapacity', () => {
  it('fits two dwellers per three-unit segment', () => {
    expect(getTrainingRoomCapacity(room())).toBe(2)
    expect(getTrainingRoomCapacity(room({ size: 9 }))).toBe(6)
  })
})

describe('isRoomAtRowEnd', () => {
  it.each([
    [7, 10, 3],
    [3, 0, 3],
    [7, 16, 9],
  ])('blocks an inner room at %i while allowing the outer room at %i', (innerX, outerX, size) => {
    const inner = { id: 'inner', coordinate_x: innerX, coordinate_y: 1, size } as Room
    const outer = { id: 'outer', coordinate_x: outerX, coordinate_y: 1, size: 3 } as Room
    const elevator = { id: 'shaft', coordinate_x: 6, coordinate_y: 1, size: 1 } as Room
    expect(isRoomAtRowEnd([inner, outer, elevator], inner)).toBe(false)
    expect(isRoomAtRowEnd([inner, outer, elevator], outer)).toBe(true)
    expect(isRoomAtRowEnd([inner, elevator], inner)).toBe(true)
  })
})

describe('manual merge candidates', () => {
  const segment = {
    id: 'source',
    name: 'Diner',
    incremental_cost: 25,
    coordinate_x: 7,
    coordinate_y: 1,
    size: 3,
    size_min: 3,
    size_max: 9,
    tier: 2,
    room_style: 'default',
  } as Room
  it('finds either neighbor while excluding gaps, mismatched tiers, and oversized merges', () => {
    const left = { ...segment, id: 'left', coordinate_x: 4 }
    const right = { ...segment, id: 'right', coordinate_x: 10 }
    const gap = { ...segment, id: 'gap', coordinate_x: 16 }
    const otherTier = { ...right, id: 'tier', tier: 1 }
    const oversized = { ...right, id: 'oversized', size: 9 }
    expect(
      getMergeCandidates([segment, right, left, gap, otherTier, oversized], segment).map(
        (r) => r.id
      )
    ).toEqual(['left', 'right'])
    expect(getMergeCandidates([left, right], { ...segment, incremental_cost: 0 })).toEqual([])
  })

  it('excludes adjacent rooms with a different theme', () => {
    const left = { ...segment, id: 'left', coordinate_x: 4, room_style: 'party' }
    const right = { ...segment, id: 'right', coordinate_x: 10 }

    expect(getMergeCandidates([left, right], segment).map((r) => r.id)).toEqual(['right'])
  })
})
