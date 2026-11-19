import { ref, watch } from 'vue'
import { defineStore } from 'pinia'
import { handleStoreError } from '@/core/utils/errorHandler'
import { useAuthStore } from '@/modules/auth/stores/auth'
import type {
  ContaminationTeamRead,
  HazardTeam,
} from '@/modules/contamination-team/models/contaminationTeam'
import { fetchResponseRoster, updateResponseTeamPlace } from '../services/responseStationService'

export const useResponseStationStore = defineStore('responseStation', () => {
  const authStore = useAuthStore()
  const roster = ref<ContaminationTeamRead | null>(null)
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const busyDwellerIds = ref<string[]>([])
  // Every load supersedes the previous one; a response only lands when it
  // belongs to the latest vault that was asked for.
  let loadVersion = 0

  function reset(): void {
    loadVersion++
    roster.value = null
    isLoading.value = false
    error.value = null
  }

  watch(() => authStore.sessionGeneration, reset, { flush: 'sync' })

  async function loadRoster(vaultId: string): Promise<void> {
    const version = ++loadVersion
    const session = authStore.sessionGeneration
    error.value = null
    if (!vaultId) {
      isLoading.value = false
      return
    }
    isLoading.value = true
    try {
      const updated = await fetchResponseRoster(vaultId)
      if (version !== loadVersion || session !== authStore.sessionGeneration) return
      roster.value = updated.vault_id === vaultId ? updated : null
    } catch (caught) {
      if (version !== loadVersion || session !== authStore.sessionGeneration) return
      roster.value = null
      error.value = handleStoreError(caught, 'Failed to load response teams', false)
    } finally {
      if (version === loadVersion) isLoading.value = false
    }
  }

  async function setPlace(
    vaultId: string,
    team: HazardTeam,
    dwellerId: string,
    active: boolean
  ): Promise<void> {
    if (!vaultId || isLoading.value || busyDwellerIds.value.length > 0) return
    const version = loadVersion
    const session = authStore.sessionGeneration
    busyDwellerIds.value = [...busyDwellerIds.value, dwellerId]
    try {
      const updated = await updateResponseTeamPlace(vaultId, team, dwellerId, active)
      if (updated && version === loadVersion && session === authStore.sessionGeneration)
        roster.value = updated
    } catch (caught) {
      if (version !== loadVersion || session !== authStore.sessionGeneration) return
      handleStoreError(caught, 'Failed to update response team')
    } finally {
      busyDwellerIds.value = busyDwellerIds.value.filter((id) => id !== dwellerId)
    }
  }

  return { roster, isLoading, error, busyDwellerIds, loadRoster, setPlace, reset }
})
