import { ref } from 'vue'
import { useRoomDestroy } from './useRoomDestroy'

export function useRoomInteractions() {
  const { destroyRoom: sharedDestroy } = useRoomDestroy()
  const selectedRoomId = ref<string | null>(null)

  const toggleRoomSelection = (roomId: string) => {
    selectedRoomId.value = selectedRoomId.value === roomId ? null : roomId
  }

  const destroyRoom = async (roomId: string, event: Event) => {
    await sharedDestroy(roomId, {
      event,
      onSuccess: () => {
        selectedRoomId.value = null
      },
    })
  }

  return {
    selectedRoomId,
    toggleRoomSelection,
    destroyRoom,
  }
}
