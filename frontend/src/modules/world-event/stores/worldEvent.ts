import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { getErrorStatus } from '@/core/types/utils'
import { handleStoreError } from '@/core/utils/errorHandler'
import { worldEventService, type WorldEvent } from '../services/worldEventService'

const ALREADY_CLAIMED = 'This event was already claimed.'

export const useWorldEventStore = defineStore('worldEvent', () => {
  const event = ref<WorldEvent | null>(null)
  const loading = ref(false)
  const claiming = ref(false)
  const claimed = ref(false)
  const error = ref<string | null>(null)
  const claimError = ref<string | null>(null)

  const hasEvent = computed(() => Boolean(event.value?.event_id))

  /** Never throws: background polls pass `silent` so a flaky tick stays quiet. */
  async function load(vaultId: string, { silent = false } = {}): Promise<void> {
    if (!event.value) loading.value = true
    try {
      event.value = await worldEventService.getEvent(vaultId)
      error.value = null
    } catch (err) {
      if (!silent) error.value = handleStoreError(err, 'Failed to load world event')
    } finally {
      loading.value = false
    }
  }

  async function claim(vaultId: string): Promise<boolean> {
    claiming.value = true
    claimError.value = null
    try {
      const result = await worldEventService.claim(vaultId)
      claimed.value = true
      if (event.value) {
        event.value = {
          ...event.value,
          can_claim: false,
          contribution: result.contribution,
        }
      }
      return true
    } catch (err) {
      if (getErrorStatus(err) === 409) claimError.value = ALREADY_CLAIMED
      else claimError.value = handleStoreError(err, 'Failed to claim reward')
      return false
    } finally {
      claiming.value = false
    }
  }

  return { event, hasEvent, loading, claiming, claimed, error, claimError, load, claim }
})

export { ALREADY_CLAIMED }
export type { WorldEvent }
