import { ref } from 'vue'
import { useRoomStore } from '@/stores/room'
import { useAuthStore } from '@/stores/auth'

export function useRoomInteractions() {
  const roomStore = useRoomStore()
  const authStore = useAuthStore()
  const selectedRoomId = ref<string | null>(null)

  const toggleRoomSelection = (roomId: string) => {
    selectedRoomId.value = selectedRoomId.value === roomId ? null : roomId
  }

  const destroyRoom = async (roomId: string, event: Event) => {
    event.stopPropagation()
    if (confirm('Are you sure you want to destroy this room?')) {
      await roomStore.destroyRoom(roomId, authStore.token as string)
      selectedRoomId.value = null
    }
  }

  return {
    selectedRoomId,
    toggleRoomSelection,
    destroyRoom
  }
}
