import { describe, expect, it } from 'vitest'
import { getRoomSegmentCount, getTrainingRoomCapacity } from '@/modules/rooms/utils/room'
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
