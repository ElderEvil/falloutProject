import { computed, ref, watch, type Ref } from 'vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useSound } from '@/core/composables/useSound'
import { getErrorMessage, notifyErrorOnce } from '@/core/utils/errorHandler'
import { useRoomStore } from '../stores/room'
import type { Room, RoomRushQuote, RoomRushResult } from '../models/room'

const BLOCKED_MESSAGES: Record<NonNullable<RoomRushQuote['blocked_reason']>, string> = {
  not_production: 'This room does not produce resources.',
  no_workers: 'Assign at least one living dweller to rush.',
  active_incident: 'Resolve the active incident before rushing.',
  no_power: 'This room is offline. Restore power first.',
  room_busy: 'Another rush is in progress. Try again.',
}

export function useRoomRush(room: Ref<Room | null>, vaultId: Ref<string>, isOpen: Ref<boolean>) {
  const roomStore = useRoomStore()
  const authStore = useAuthStore()
  const { playSound } = useSound()
  const quote = ref<RoomRushQuote | null>(null)
  const result = ref<RoomRushResult | null>(null)
  const error = ref<string | null>(null)
  const isLoadingQuote = ref(false)
  const isRushing = ref(false)
  const showConfirmation = ref(false)

  const blockedMessage = computed(() => {
    const reason = quote.value?.blocked_reason
    return reason ? BLOCKED_MESSAGES[reason] : ''
  })

  async function loadQuote(silent = false): Promise<void> {
    if (!room.value || !authStore.token) {
      quote.value = null
      return
    }
    if (!silent) isLoadingQuote.value = true
    error.value = null
    try {
      quote.value = await roomStore.fetchRushQuote(room.value.id, authStore.token)
    } catch (caught) {
      quote.value = null
      error.value = getErrorMessage(caught)
    } finally {
      if (!silent) isLoadingQuote.value = false
    }
  }

  function requestRush(): void {
    if (!quote.value?.can_rush || isRushing.value) return
    showConfirmation.value = true
  }

  function cancelRush(): void {
    showConfirmation.value = false
  }

  function clearRushResult(): void {
    result.value = null
  }

  async function confirmRush(): Promise<void> {
    if (!room.value || !quote.value?.can_rush || !authStore.token || isRushing.value) return
    const roomId = room.value.id
    const token = authStore.token
    const currentVaultId = vaultId.value
    showConfirmation.value = false
    isRushing.value = true
    error.value = null
    playSound('rushGo', 'sfx')
    try {
      const outcome = await roomStore.rushRoom(roomId, token, currentVaultId)
      if (room.value?.id !== roomId) return
      result.value = outcome
      if (quote.value) {
        quote.value = {
          ...quote.value,
          stacks: outcome.stacks_after,
          fail_chance: outcome.next_fail_chance,
          success_chance: 100 - outcome.next_fail_chance,
        }
      }
      await loadQuote(true)
    } catch (caught) {
      error.value = getErrorMessage(caught)
      notifyErrorOnce(caught, error.value, 5000)
    } finally {
      isRushing.value = false
    }
  }

  watch(
    [() => room.value?.id, isOpen],
    ([, open]) => {
      if (!open) {
        quote.value = null
        result.value = null
        error.value = null
        return
      }
      result.value = null
      void loadQuote()
    },
    { immediate: true }
  )

  return {
    quote,
    result,
    error,
    isLoadingQuote,
    isRushing,
    showConfirmation,
    blockedMessage,
    loadQuote,
    requestRush,
    cancelRush,
    confirmRush,
    clearRushResult,
  }
}
