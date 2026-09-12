import { computed, type Ref } from 'vue'
import type { Room } from '@/modules/rooms/models/room'

export function useRoomLookup(rooms: Ref<Room[]>) {
  const roomsById = computed(() => new Map(rooms.value.map((room) => [room.id, room])))

  const roomFor = (roomId: string | null | undefined) =>
    roomId ? roomsById.value.get(roomId) : undefined

  const roomName = (roomId: string | null | undefined) => roomFor(roomId)?.name

  return { roomFor, roomName }
}
