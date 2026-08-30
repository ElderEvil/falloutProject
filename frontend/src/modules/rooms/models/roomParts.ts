import type { Room } from './room'

/**
 * Ordered sections the room detail modal renders, decided in one place.
 * Phase 1 keeps each room type's composition exactly as before — only the
 * decision point moved here (roadmap: Room Detail Part Registry).
 */
export type RoomPart =
  | 'preview'
  | 'info'
  | 'productionStats'
  | 'radioStats'
  | 'dwellerList'
  | 'arena'
  | 'overseerBriefing'
  | 'actions'
  | 'radioControls'

// Special rooms are identified by their seed-data-stable names; the string
// matching lives here and nowhere else.
export function isRadioRoom(room: Room | null): boolean {
  return room?.name.toLowerCase().includes('radio') ?? false
}

export function isVaultDoor(room: Room | null): boolean {
  return room?.name.toLowerCase() === 'vault door'
}

export function isOverseersOffice(room: Room | null): boolean {
  return room?.name.toLowerCase() === "overseer's office"
}

/** A room contributes to resource production when it is a production room with an ability. */
export function producesResources(room: Room | null): boolean {
  return room?.category.toLowerCase() === 'production' && !!room.ability
}

export function getRoomDetailParts(room: Room | null): RoomPart[] {
  if (!room) return []

  // The arena detail renders its own preview + fight state instead of the
  // generic sections.
  if (room.category.toLowerCase() === 'arena') return ['arena']

  const parts: RoomPart[] = ['preview', 'info']
  if (isOverseersOffice(room)) parts.push('overseerBriefing')
  if (isRadioRoom(room)) parts.push('radioStats')
  else if (producesResources(room)) parts.push('productionStats')
  parts.push('dwellerList', 'actions')
  if (isRadioRoom(room)) parts.push('radioControls')
  return parts
}

export function hasPart(parts: RoomPart[], part: RoomPart): boolean {
  return parts.includes(part)
}
