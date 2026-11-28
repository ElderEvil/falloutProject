import { ref } from 'vue'
import { defineStore } from 'pinia'
import { apiGet } from '@/core/utils/api'
import { handleStoreError } from '@/core/utils/errorHandler'
import type { components } from '@/core/types/api.generated'

type FeaturesResponse = components['schemas']['FeaturesResponse']

// Defaults mirror the shipped backend defaults so first paint never offers what the API would reject.
export const useFeatureFlagsStore = defineStore('featureFlags', () => {
  const raceMechanics = ref(true)
  const factionMechanics = ref(false)
  const worldEvents = ref(false)
  const pvpDuels = ref(false)
  const combatZone = ref(false)
  const vaultDiplomacy = ref(false)
  const loaded = ref(false)

  // Concurrent callers share one request; a failed fetch stays unloaded so a later mount retries.
  let inFlight: Promise<void> | null = null

  function fetchFlags(): Promise<void> {
    if (loaded.value) return Promise.resolve()
    inFlight ??= (async () => {
      try {
        const flags = await apiGet<FeaturesResponse>('/api/v1/system/features')
        raceMechanics.value = flags.race_mechanics
        factionMechanics.value = flags.faction_mechanics
        worldEvents.value = flags.world_events
        pvpDuels.value = flags.pvp_duels
        combatZone.value = flags.combat_zone
        vaultDiplomacy.value = flags.vault_diplomacy
        loaded.value = true
      } catch (error) {
        handleStoreError(error, 'Failed to load feature flags', false)
      } finally {
        inFlight = null
      }
    })()
    return inFlight
  }

  return {
    raceMechanics,
    factionMechanics,
    worldEvents,
    pvpDuels,
    combatZone,
    vaultDiplomacy,
    loaded,
    fetchFlags,
  }
})
