import type { components } from '@/core/types/api.generated'

// Re-export generated API types
export type Room = components['schemas']['RoomRead']
export type RoomBuild = components['schemas']['RoomBuild']
export type RoomTemplate = components['schemas']['RoomCreateWithoutVaultID']

export type RoomStyleValue = 'default' | 'party'

export const PARTY_STYLE_ROOMS = new Set(['Diner', 'Living room'])

export function supportsPartyStyle(room: Pick<Room, 'name'>): boolean {
  return PARTY_STYLE_ROOMS.has(room.name)
}

export function roomStyle(room: Pick<Room, 'room_style'>): RoomStyleValue {
  return room.room_style === 'party' ? 'party' : 'default'
}
