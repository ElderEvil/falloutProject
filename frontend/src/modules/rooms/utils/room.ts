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

/**
 * A level is buildable when it has an elevator on it. Row 0 is always
 * buildable because the vault door anchors it.
 */
export function isLevelBuildable(rooms: Room[], level: number): boolean {
  if (level === 0) return true
  return rooms.some(
    (r) => r.name.toLowerCase() === 'elevator' && (r.coordinate_y ?? -1) === level
  )
}

/**
 * Elevators stack vertically: a new elevator at (x, y) requires an existing
 * elevator directly above it at (x, y - 1).
 */
export function hasElevatorAbove(rooms: Room[], x: number, y: number): boolean {
  return rooms.some(
    (r) => r.name.toLowerCase() === 'elevator' && r.coordinate_x === x && (r.coordinate_y ?? -1) === y - 1
  )
}
