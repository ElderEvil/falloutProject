import { ref, type Ref } from 'vue'
import { useRoute } from 'vue-router'
import { useRoomStore } from '@/modules/rooms/stores/room'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useToast } from '@/core/composables/useToast'

interface DestroyRoomOptions {
  event?: Event
  roomName?: string
  actionError?: Ref<string | null>
  onSuccess?: () => void
}

export function useRoomDestroy() {
  const route = useRoute()
  const roomStore = useRoomStore()
  const authStore = useAuthStore()
  const toast = useToast()

  const isDestroying = ref(false)

  async function destroyRoom(roomId: string, options?: DestroyRoomOptions): Promise<void> {
    options?.event?.stopPropagation()

    const name = options?.roomName || 'this room'
    if (!confirm(`Are you sure you want to destroy ${name}? You will receive a partial refund.`)) {
      return
    }

    isDestroying.value = true
    if (options?.actionError) options.actionError.value = null

    const vaultId = route.params.id
    if (!vaultId || typeof vaultId !== 'string') {
      if (options?.actionError) options.actionError.value = 'No vault ID available'
      isDestroying.value = false
      return
    }

    const token = authStore.token
    if (!token || typeof token !== 'string') {
      if (options?.actionError) options.actionError.value = 'No auth token available'
      isDestroying.value = false
      return
    }

    try {
      await roomStore.destroyRoom(roomId, token, vaultId)
      toast.success(`${options?.roomName || 'Room'} destroyed. Caps refunded (50%).`)
      options?.onSuccess?.()
    } catch (error) {
      console.error('Failed to destroy room:', error)
      const message = error instanceof Error ? error.message : 'Failed to destroy room'
      if (options?.actionError) options.actionError.value = message
      toast.error(message, 5000)
    } finally {
      isDestroying.value = false
    }
  }

  return {
    isDestroying,
    destroyRoom,
  }
}
