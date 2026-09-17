import { ref } from 'vue'
import { defineStore } from 'pinia'
import { getFeatureFlags } from '@/modules/dwellers/services/dwellerService'
import { handleStoreError } from '@/core/utils/errorHandler'

/**
 * Backend feature switches. Defaults match the shipped backend defaults so the
 * first paint never offers what the API would reject; components refresh on mount.
 */
export const useFeatureFlagsStore = defineStore('featureFlags', () => {
  const raceMechanics = ref(true)
  const factionMechanics = ref(false)
  const loaded = ref(false)

  // Concurrent callers share one request: the panel and the roster mount together, and a
  // caller that returned early would read the pre-fetch defaults. A failed fetch stays
  // unloaded so a later mount can retry.
  let inFlight: Promise<void> | null = null

  function fetchFlags(): Promise<void> {
    if (loaded.value) return Promise.resolve()
    inFlight ??= (async () => {
      try {
        const flags = await getFeatureFlags()
        raceMechanics.value = flags.race_mechanics
        factionMechanics.value = flags.faction_mechanics
        loaded.value = true
      } catch (error) {
        handleStoreError(error, 'Failed to load feature flags', false)
      } finally {
        inFlight = null
      }
    })()
    return inFlight
  }

  return { raceMechanics, factionMechanics, loaded, fetchFlags }
})
