import type { Room } from './room'

/** Curated detail backgrounds; grid sprites remain the backend image_url contract. */
export const ARENA_DETAIL_SCENE = '/assets/room-scenes/arena-industrial-v1.webp'

export function getRoomDetailScene(
  room: Pick<Room, 'name' | 'category' | 'tier'> | null
): string | null {
  if (!room || ![1, 2, 3].includes(room.tier)) return null
  return room.name.trim().toLowerCase() === 'arena' && room.category.toLowerCase() === 'arena'
    ? ARENA_DETAIL_SCENE
    : null
}
