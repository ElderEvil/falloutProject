import type { Room } from '@/modules/rooms/models/room'

/**
 * Compute the capacity for a room.
 *
 * Rooms fit 2 dwellers per 3-tile segment; arena rooms park challengers the
 * same way (two of them are then picked as fighters). Falls back to `size_min`
 * when `size` is missing and defaults to a 3-tile room.
 */
export function getTrainingRoomCapacity(room: Pick<Room, 'size' | 'size_min'>): number {
  const size = room.size ?? room.size_min ?? 3
  return Math.ceil(size / 3) * 2
}
