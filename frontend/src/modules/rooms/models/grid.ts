/** Unit-grid geometry shared by the vault grid, placement, and hover preview.
 *
 * A floor is `FLOOR_UNITS` units wide: the vault door region holds two room
 * slots, the elevator shaft occupies a single unit, and eight room slots follow.
 * Rooms are 3 units each, so build slots start at the constants below.
 */

export const UNITS_PER_ROOM = 3
export const FLOOR_UNITS = 28
export const SHAFT_X = 6

export const LEFT_SLOT_STARTS = [0, UNITS_PER_ROOM]
export const RIGHT_SLOT_STARTS = Array.from(
  { length: 7 },
  (_, index) => SHAFT_X + 1 + index * UNITS_PER_ROOM
)
export const ROOM_SLOT_STARTS = [...LEFT_SLOT_STARTS, ...RIGHT_SLOT_STARTS]
