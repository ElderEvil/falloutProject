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

/** Unique and fixed-width facilities keep their single-room identity. */
export function canRemodelRoom(room: Room): boolean {
  return (
    !!room.incremental_cost &&
    room.size_max > room.size_min &&
    room.coordinate_x != null &&
    room.coordinate_y != null &&
    (room.size ?? room.size_min) % room.size_min === 0
  )
}

export function getMergeCandidates(rooms: Room[], room: Room): Room[] {
  if (!canRemodelRoom(room)) return []
  const x = room.coordinate_x!
  const size = room.size ?? room.size_min
  return rooms
    .filter(
      (other) =>
        other.id !== room.id &&
        canRemodelRoom(other) &&
        other.name === room.name &&
        other.tier === room.tier &&
        other.size_min === room.size_min &&
        other.coordinate_y === room.coordinate_y &&
        size + (other.size ?? other.size_min) <= Math.min(room.size_max, other.size_max) &&
        (x + size === other.coordinate_x ||
          other.coordinate_x! + (other.size ?? other.size_min) === x)
    )
    .sort((a, b) => a.coordinate_x! - b.coordinate_x!)
}
