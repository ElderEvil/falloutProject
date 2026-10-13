import type { Room } from './room'

/** Curated backgrounds shared by room previews and grid cells. */
export const ARENA_DETAIL_SCENES: Record<number, string> = {
  1: '/assets/room-scenes/arena-cartoon-tier-1-v1.webp',
  2: '/assets/room-scenes/arena-cartoon-tier-2-v1.webp',
  3: '/assets/room-scenes/arena-cartoon-tier-3-v1.webp',
}

export function getRoomDetailScene(
  room: Pick<Room, 'name' | 'category' | 'tier'> | null
): string | null {
  if (!room || ![1, 2, 3].includes(room.tier)) return null
  return room.name.trim().toLowerCase() === 'arena' && room.category.toLowerCase() === 'arena'
    ? (ARENA_DETAIL_SCENES[room.tier] ?? null)
    : null
}
