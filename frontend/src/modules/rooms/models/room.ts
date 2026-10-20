import type { components } from '@/core/types/api.generated'

// Re-export generated API types
export type Room = components['schemas']['RoomRead']
export type RoomBuild = components['schemas']['RoomBuild']
export type RoomTemplate = components['schemas']['RoomCreateWithoutVaultID']

export type RoomStyleValue =
  | 'default'
  | 'party'
  | 'brotherhood'
  | 'halloween'
  | 'institute'
  | 'minutemen'
  | 'railroad'
  | 'thanksgiving'
  | 'xmas'

export const ROOM_STYLES: { value: RoomStyleValue; label: string }[] = [
  { value: 'default', label: 'Standard' },
  { value: 'party', label: 'Party' },
  { value: 'brotherhood', label: 'Brotherhood' },
  { value: 'halloween', label: 'Halloween' },
  { value: 'institute', label: 'Institute' },
  { value: 'minutemen', label: 'Minutemen' },
  { value: 'railroad', label: 'Railroad' },
  { value: 'thanksgiving', label: 'Thanksgiving' },
  { value: 'xmas', label: 'Christmas' },
]

export const THEMED_ROOM_NAMES = new Set(['Diner', 'Living room'])

export function supportsRoomStyles(room: Pick<Room, 'name'>): boolean {
  return THEMED_ROOM_NAMES.has(room.name)
}

export function roomStyle(room: Pick<Room, 'room_style'>): RoomStyleValue {
  return ROOM_STYLES.some((style) => style.value === room.room_style)
    ? (room.room_style as RoomStyleValue)
    : 'default'
}
