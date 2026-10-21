import { onScopeDispose, ref, watch, type Ref } from 'vue'
import { useConfirmDialog } from '@vueuse/core'
import { isRoomAtRowEnd } from '../utils/room'
import { notifyErrorOnce, getErrorMessage } from '@/core/utils/errorHandler'
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
  const destroyTitle = ref('')
  const {
    isRevealed: showDestroyConfirmation,
    reveal: revealDestroy,
    confirm: confirmDestroy,
    cancel: cancelDestroy,
  } = useConfirmDialog()
  onScopeDispose(cancelDestroy)
  watch([() => route.params.id, () => authStore.token], () => cancelDestroy())

  async function destroyRoom(roomId: string, options?: DestroyRoomOptions): Promise<void> {
    options?.event?.stopPropagation()
    if (isDestroying.value || showDestroyConfirmation.value) return

    const room = roomStore.rooms.find((r) => r.id === roomId)
    if (room && room.name.toLowerCase() !== 'elevator' && !isRoomAtRowEnd(roomStore.rooms, room)) {
      const message =
        'Only rooms at the end of a row can be destroyed. Remove the outer rooms first.'
      if (options?.actionError) options.actionError.value = message
      toast.error(message)
      return
    }

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

    const name = options?.roomName || room?.name || 'this room'
    destroyTitle.value = `Destroy ${name}?`
    const { isCanceled } = await revealDestroy()
    if (isCanceled || route.params.id !== vaultId || authStore.token !== token) return
    isDestroying.value = true
    if (options?.actionError) options.actionError.value = null

    try {
      await roomStore.destroyRoom(roomId, token, vaultId)
      toast.success(`${options?.roomName || 'Room'} destroyed. Caps refunded (50%).`)
      options?.onSuccess?.()
    } catch (error) {
      const message = getErrorMessage(error)
      if (options?.actionError) options.actionError.value = message
      notifyErrorOnce(error, message, 5000)
    } finally {
      isDestroying.value = false
    }
  }

  return {
    isDestroying,
    destroyTitle,
    showDestroyConfirmation,
    confirmDestroy,
    cancelDestroy,
    destroyRoom,
  }
}
