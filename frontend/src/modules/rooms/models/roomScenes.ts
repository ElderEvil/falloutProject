import type { Room } from './room'

/** Curated backgrounds shared by room previews and grid cells. */
export const ARENA_DETAIL_SCENES: Record<number, string> = {
  1: '/assets/room-scenes/arena-cartoon-tier-1-v1.webp',
  2: '/assets/room-scenes/arena-cartoon-tier-2-v1.webp',
  3: '/assets/room-scenes/arena-cartoon-tier-3-v1.webp',
}

export const RESPONSE_DETAIL_SCENES: Record<number, string> = {
  3: '/assets/room-scenes/response-bay-size-3-v1.webp',
  6: '/assets/room-scenes/response-bay-size-6-v1.webp',
  9: '/assets/room-scenes/response-bay-size-9-v1.webp',
}

export function getRoomDetailScene(
  room: (Pick<Room, 'name' | 'category' | 'tier'> & Partial<Pick<Room, 'size' | 'size_min'>>) | null
): string | null {
  if (!room || ![1, 2, 3].includes(room.tier)) return null
  if (room.category.toLowerCase() === 'response')
    return RESPONSE_DETAIL_SCENES[room.size ?? room.size_min ?? 3] ?? null
  return room.name.trim().toLowerCase() === 'arena' && room.category.toLowerCase() === 'arena'
    ? (ARENA_DETAIL_SCENES[room.tier] ?? null)
    : null
}
