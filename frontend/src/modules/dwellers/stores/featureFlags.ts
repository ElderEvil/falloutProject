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
  const loading = ref(false)

  async function fetchFlags(): Promise<void> {
    if (loaded.value || loading.value) return
    loading.value = true
    try {
      const flags = await getFeatureFlags()
      raceMechanics.value = flags.race_mechanics
      factionMechanics.value = flags.faction_mechanics
    } catch (error) {
      handleStoreError(error, 'Failed to load feature flags', false)
    } finally {
      loading.value = false
      loaded.value = true
    }
  }

  return { raceMechanics, factionMechanics, loaded, fetchFlags }
})
