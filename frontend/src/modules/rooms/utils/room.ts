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
 * How many base segments a room occupies. Merged rooms span more than one, and
 * build/upgrade/refund costs are charged per segment.
 */
export function getRoomSegmentCount(room: Pick<Room, 'size' | 'size_min'>): number {
  const size = room.size ?? room.size_min ?? 3
  const minSize = room.size_min ?? 3
  return Math.max(Math.floor(size / minSize), 1)
}

/**
 * A level is buildable when it has an elevator on it. Row 0 is always
 * buildable because the vault door anchors it.
 */
export function isLevelBuildable(rooms: Room[], level: number): boolean {
  if (level === 0) return true
  return rooms.some((r) => r.name.toLowerCase() === 'elevator' && (r.coordinate_y ?? -1) === level)
}

/**
 * Elevators stack vertically: a new elevator at (x, y) requires an existing
 * elevator directly above it at (x, y - 1).
 */
export function hasElevatorAbove(rooms: Room[], x: number, y: number): boolean {
  return rooms.some(
    (r) =>
      r.name.toLowerCase() === 'elevator' &&
      r.coordinate_x === x &&
      (r.coordinate_y ?? -1) === y - 1
  )
}

/** Only outer rooms may be removed; inner rooms keep the row connected. */
export function isRoomAtRowEnd(rooms: Room[], room: Room): boolean {
  const start = room.coordinate_x
  if (start == null) return true
  const end = start + (room.size ?? room.size_min)
  const others = rooms.filter(
    (r) => r.id !== room.id && r.coordinate_y === room.coordinate_y && r.coordinate_x != null
  )
  return (
    !others.some((r) => r.coordinate_x! + (r.size ?? r.size_min) <= start) ||
    !others.some((r) => r.coordinate_x! >= end)
  )
}
