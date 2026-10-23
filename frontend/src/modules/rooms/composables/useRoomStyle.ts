import { ref, type Ref } from 'vue'
import { useRoute } from 'vue-router'
import type { Room, RoomStyleValue } from '../models/room'
import { roomStyleLabel } from '../models/room'
import { useRoomStore } from '../stores/room'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useToast } from '@/core/composables/useToast'
import { notifyErrorOnce, getErrorMessage } from '@/core/utils/errorHandler'

export function useRoomStyle(
  room: Ref<Room | null>,
  actionError: Ref<string | null>,
  emitRoomUpdated: () => void
) {
  const route = useRoute()
  const roomStore = useRoomStore()
  const authStore = useAuthStore()
  const toast = useToast()
  const isApplyingStyle = ref(false)

  async function handleApplyStyle(style: RoomStyleValue) {
    if (!room.value || isApplyingStyle.value) return
    const vaultId = route.params.id
    const token = authStore.token
    if (!vaultId || typeof vaultId !== 'string' || !token) {
      actionError.value = 'Unable to apply room style right now'
      return
    }

    isApplyingStyle.value = true
    actionError.value = null
    try {
      await roomStore.applyRoomStyle(room.value.id, style, token)
      toast.success(
        style === 'default' ? 'Standard theme restored.' : `${roomStyleLabel(style)} theme applied.`
      )
      emitRoomUpdated()
    } catch (error) {
      actionError.value = getErrorMessage(error)
      notifyErrorOnce(error, actionError.value)
    } finally {
      isApplyingStyle.value = false
    }
  }

  return { isApplyingStyle, handleApplyStyle }
}
