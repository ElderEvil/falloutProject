import { computed, ref } from 'vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { isMature, type Dweller } from '@/modules/dwellers/models/dweller'
import { useExplorationStore } from '@/modules/exploration/stores/exploration'
import { explorationApi } from '@/modules/exploration/api/exploration'
import { useToast } from '@/core/composables/useToast'

/** Search length used for the modal's initial suggestion before a duration is picked. */
const DEFAULT_SUGGEST_DURATION = 4

export interface PendingExplorer {
  dwellerId: string
  firstName: string
  lastName?: string
  /** Compass degrees (0-360, clockwise from north) for a heading-bearing run. */
  headingDegrees?: number
}

/** Values to seed the modal's reset-on-open; undefined keeps today's defaults. */
export interface WastelandPrefill {
  duration?: number
  stimpaks?: number
  radaways?: number
}

/**
 * Shared "send a dweller to the wasteland via the duration modal" flow, used by
 * the WastelandPanel and the dweller detail page. Owns the modal open/close
 * state and the confirm action.
 */
export function useSendToWasteland(vaultId: () => string | null) {
  const authStore = useAuthStore()
  const { filter: dwellerStore } = useDwellerStore()
  const explorationStore = useExplorationStore()
  const toast = useToast()

  const showModal = ref(false)
  const pendingDweller = ref<PendingExplorer | null>(null)
  const pendingPrefill = ref<WastelandPrefill | null>(null)
  const isSending = ref(false)
  const suggestedHeading = ref<number | null>(null)
  const isSuggestingHeading = ref(false)
  let suggestionToken = 0
  let lastSuggestDuration = DEFAULT_SUGGEST_DURATION

  // A map click supplies the heading; otherwise the server suggests one.
  const headingDegrees = computed<number | null>(
    () => pendingDweller.value?.headingDegrees ?? suggestedHeading.value
  )

  const suggestHeading = async (duration: number) => {
    const vId = vaultId()
    if (!vId || !authStore.token) return
    lastSuggestDuration = duration
    const token = ++suggestionToken
    isSuggestingHeading.value = true
    try {
      const heading = await explorationApi.suggestHeading(
        authStore.token,
        vId,
        crypto.randomUUID(),
        duration
      )
      if (token === suggestionToken) suggestedHeading.value = heading
    } catch {
      if (token === suggestionToken) suggestedHeading.value = null
    } finally {
      if (token === suggestionToken) isSuggestingHeading.value = false
    }
  }

  const reroll = (duration: number = lastSuggestDuration) => {
    // A manual pick wins until the user explicitly re-rolls: clear it and let
    // the server suggest a fresh direction for the new duration.
    if (pendingDweller.value && pendingDweller.value.headingDegrees !== undefined) {
      pendingDweller.value = { ...pendingDweller.value, headingDegrees: undefined }
    }
    void suggestHeading(duration)
  }

  /** Store a compass pick from the modal; it overrides the server suggestion. */
  const setHeading = (degrees: number) => {
    if (!pendingDweller.value) return
    pendingDweller.value = { ...pendingDweller.value, headingDegrees: degrees }
  }

  const open = (
    dweller: PendingExplorer,
    knownDweller?: Pick<Dweller, 'age_group'>,
    prefill?: WastelandPrefill
  ) => {
    const candidate =
      knownDweller ?? dwellerStore.dwellers.find((subject) => subject.id === dweller.dwellerId)
    if (candidate && !isMature(candidate)) {
      toast.error(`${dweller.firstName} is too young for the wasteland`)
      return
    }
    suggestionToken++
    isSuggestingHeading.value = false
    pendingDweller.value = dweller
    pendingPrefill.value = prefill ?? null
    suggestedHeading.value = null
    showModal.value = true
    if (dweller.headingDegrees === undefined) {
      // A prefilled duration drives the first suggestion so the auto heading
      // matches the duration the modal opens with.
      void suggestHeading(prefill?.duration ?? DEFAULT_SUGGEST_DURATION)
    }
  }

  const cancel = () => {
    suggestionToken++
    isSuggestingHeading.value = false
    showModal.value = false
    pendingDweller.value = null
    pendingPrefill.value = null
    suggestedHeading.value = null
  }

  const confirm = async (
    payload: { duration: number; stimpaks: number; radaways: number },
    refresh?: () => Promise<void>
  ): Promise<boolean> => {
    const vId = vaultId()
    if (!pendingDweller.value || !vId || !authStore.token || isSending.value) return false

    isSending.value = true
    const { dwellerId, firstName, lastName } = pendingDweller.value
    const heading = pendingDweller.value.headingDegrees ?? suggestedHeading.value
    let dispatched = false
    try {
      await explorationStore.sendDwellerToWasteland(
        vId,
        dwellerId,
        payload.duration,
        authStore.token,
        payload.stimpaks,
        payload.radaways,
        heading ?? undefined
      )
      toast.success(`${firstName} ${lastName ?? ''} sent to the wasteland for ${payload.duration} hour(s)!`)
      showModal.value = false
      pendingDweller.value = null
      pendingPrefill.value = null
      suggestedHeading.value = null
      dispatched = true
    } catch {
      toast.error('Failed to send dweller to wasteland')
      return false
    } finally {
      isSending.value = false
    }

    // Refresh is best-effort: a refresh failure must not mask a successful dispatch.
    if (dispatched && refresh) {
      try {
        await refresh()
      } catch {
        // dispatch already succeeded; ignore refresh errors
      }
    }
    return dispatched
  }

  return {
    showModal,
    pendingDweller,
    pendingPrefill,
    headingDegrees,
    isSuggestingHeading,
    isSending,
    open,
    cancel,
    confirm,
    reroll,
    setHeading,
  }
}
