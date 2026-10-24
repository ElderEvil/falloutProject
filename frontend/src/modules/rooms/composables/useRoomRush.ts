import { computed, getCurrentScope, onScopeDispose, ref, watch, type Ref } from 'vue'
import { useSound } from '@/core/composables/useSound'
import { useVaultBoyFeedback } from '@/core/composables/useVaultBoyFeedback'
import { getErrorMessage, notifyErrorOnce } from '@/core/utils/errorHandler'
import { useRoomStore } from '../stores/room'
import type { Room, RoomRushQuote } from '../models/room'
import { formatRushResult } from '../utils/roomRush'

const BLOCKED_MESSAGES: Record<NonNullable<RoomRushQuote['blocked_reason']>, string> = {
  not_production: 'This room does not produce resources.',
  no_workers: 'Assign at least one living dweller to rush.',
  active_incident: 'Resolve the active incident before rushing.',
  no_power: 'This room is offline. Restore power first.',
  room_busy: 'Another rush is in progress. Try again.',
}

const RUSH_FEEDBACK_DELAY_MS = 1200
const RUSH_FEEDBACK_DURATION_MS = 1600

export function useRoomRush(room: Ref<Room | null>, vaultId: Ref<string>, isOpen: Ref<boolean>) {
  const roomStore = useRoomStore()
  const feedback = useVaultBoyFeedback()
  const { playSound, stopSound } = useSound()
  const quote = ref<RoomRushQuote | null>(null)
  const error = ref<string | null>(null)
  const isLoadingQuote = ref(false)
  const isRushing = ref(false)
  const showRushDialog = ref(false)
  let quoteRequestSequence = 0
  let rushSessionGeneration = 0
  let rushFeedbackTimer: ReturnType<typeof setTimeout> | null = null

  function clearRushFeedbackTimer(): void {
    if (rushFeedbackTimer !== null) {
      clearTimeout(rushFeedbackTimer)
      rushFeedbackTimer = null
    }
  }

  const blockedMessage = computed(() => {
    const reason = quote.value?.blocked_reason
    return reason ? BLOCKED_MESSAGES[reason] : ''
  })

  function resetRush(): void {
    clearRushFeedbackTimer()
    quoteRequestSequence += 1
    rushSessionGeneration += 1
    stopSound('rushMode')
    showRushDialog.value = false
    quote.value = null
    error.value = null
    isLoadingQuote.value = false
    isRushing.value = false
  }

  async function loadQuote(): Promise<void> {
    const requestSequence = ++quoteRequestSequence
    if (!room.value) {
      quote.value = null
      isLoadingQuote.value = false
      return
    }
    const requestedRoomId = room.value.id
    isLoadingQuote.value = true
    quote.value = null
    error.value = null
    try {
      const nextQuote = await roomStore.fetchRushQuote(requestedRoomId)
      if (requestSequence !== quoteRequestSequence || room.value?.id !== requestedRoomId) return
      quote.value = nextQuote
    } catch (caught) {
      if (requestSequence !== quoteRequestSequence || room.value?.id !== requestedRoomId) return
      quote.value = null
      error.value = getErrorMessage(caught)
    } finally {
      if (requestSequence === quoteRequestSequence && room.value?.id === requestedRoomId) {
        isLoadingQuote.value = false
      }
    }
  }

  function requestRush(): void {
    if (!room.value || isRushing.value) return
    clearRushFeedbackTimer()
    showRushDialog.value = true
    error.value = null
    playSound('rushMode', 'music')
    void loadQuote()
  }

  function cancelRush(): void {
    clearRushFeedbackTimer()
    stopSound('rushMode')
    showRushDialog.value = false
    quoteRequestSequence += 1
    if (isRushing.value) {
      rushSessionGeneration += 1
      isRushing.value = false
    }
    quote.value = null
    error.value = null
    isLoadingQuote.value = false
  }

  async function confirmRush(): Promise<void> {
    if (!room.value || !quote.value?.can_rush || isRushing.value) return
    const roomId = room.value.id
    const currentVaultId = vaultId.value
    const requestGeneration = rushSessionGeneration
    isRushing.value = true
    error.value = null
    stopSound('rushMode')
    playSound('rushGo', 'sfx')
    try {
      const outcome = await roomStore.rushRoom(roomId, currentVaultId)
      if (requestGeneration !== rushSessionGeneration || room.value?.id !== roomId) return
      showRushDialog.value = false
      quote.value = null
      const isSuccess = outcome.outcome === 'success'
      const gainedResource =
        isSuccess &&
        (Object.values(outcome.payout).some((amount) => amount > 0) || outcome.caps > 0)
      clearRushFeedbackTimer()
      rushFeedbackTimer = setTimeout(() => {
        rushFeedbackTimer = null
        if (requestGeneration !== rushSessionGeneration || room.value?.id !== roomId) return
        playSound(isSuccess ? 'rushSuccess' : 'rushFail', 'sfx')
        if (gainedResource) playSound('resourceCollected', 'sfx')
        if (currentVaultId) {
          feedback.show(
            {
              animation: isSuccess ? 'rush-success' : 'rush-failure',
              title: isSuccess ? 'RUSH OK' : 'RUSH FAIL',
              message: formatRushResult(outcome),
              vaultId: currentVaultId,
              durationMs: RUSH_FEEDBACK_DURATION_MS,
            },
            { priority: true }
          )
        }
      }, RUSH_FEEDBACK_DELAY_MS)
    } catch (caught) {
      if (requestGeneration !== rushSessionGeneration || room.value?.id !== roomId) return
      error.value = getErrorMessage(caught)
      notifyErrorOnce(caught, error.value, 5000)
    } finally {
      if (requestGeneration === rushSessionGeneration) isRushing.value = false
    }
  }

  watch([() => room.value?.id, isOpen], resetRush, { immediate: true })

  if (getCurrentScope()) {
    onScopeDispose(() => {
      clearRushFeedbackTimer()
      stopSound('rushMode')
      quoteRequestSequence += 1
      rushSessionGeneration += 1
    })
  }

  return {
    quote,
    error,
    isLoadingQuote,
    isRushing,
    showRushDialog,
    blockedMessage,
    requestRush,
    cancelRush,
    confirmRush,
  }
}
