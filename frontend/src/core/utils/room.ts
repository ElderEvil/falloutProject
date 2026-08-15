import type { Room } from '@/modules/rooms/models/room'

/**
 * Compute the training capacity for a room.
 *
 * Training rooms fit 2 dwellers per 3-tile segment. Falls back to
 * `size_min` when `size` is missing and defaults to a 3-tile room.
 */
export function getTrainingRoomCapacity(room: Pick<Room, 'size' | 'size_min'>): number {
  const size = room.size ?? room.size_min ?? 3
  return Math.ceil(size / 3) * 2
}
