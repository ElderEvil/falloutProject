import { ref } from 'vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useExplorationStore } from '@/modules/exploration/stores/exploration'
import { useToast } from '@/core/composables/useToast'

export interface PendingExplorer {
  dwellerId: string
  firstName: string
  lastName?: string
  currentRoomId?: string | null
}

/**
 * Shared "send a dweller to the wasteland via the duration modal" flow, used by
 * the WastelandPanel and the dweller detail page. Owns the modal open/close
 * state and the confirm action (unassign-from-room if needed, then send).
 */
export function useSendToWasteland(vaultId: () => string | null) {
  const authStore = useAuthStore()
  const { management: dwellerManagementStore } = useDwellerStore()
  const explorationStore = useExplorationStore()
  const toast = useToast()

  const showModal = ref(false)
  const pendingDweller = ref<PendingExplorer | null>(null)
  const isSending = ref(false)

  const open = (dweller: PendingExplorer) => {
    pendingDweller.value = dweller
    showModal.value = true
  }

  const cancel = () => {
    showModal.value = false
    pendingDweller.value = null
  }

  const confirm = async (
    payload: { duration: number; stimpaks: number; radaways: number },
    refresh?: () => Promise<void>
  ): Promise<boolean> => {
    const vId = vaultId()
    if (!pendingDweller.value || !vId || !authStore.token || isSending.value) return false

    isSending.value = true
    const { dwellerId, firstName, lastName, currentRoomId } = pendingDweller.value
    try {
      if (currentRoomId) {
        await dwellerManagementStore.unassignDwellerFromRoom(dwellerId, authStore.token)
      }
      await explorationStore.sendDwellerToWasteland(
        vId,
        dwellerId,
        payload.duration,
        authStore.token,
        payload.stimpaks,
        payload.radaways
      )
      toast.success(`${firstName} ${lastName ?? ''} sent to the wasteland for ${payload.duration} hour(s)!`)
      showModal.value = false
      pendingDweller.value = null
      await refresh?.()
      return true
    } catch {
      toast.error('Failed to send dweller to wasteland')
      return false
    } finally {
      isSending.value = false
    }
  }

  return { showModal, pendingDweller, isSending, open, cancel, confirm }
}
