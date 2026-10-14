import { ref } from 'vue'
import { defineStore } from 'pinia'
import { handleStoreError } from '@/core/utils/errorHandler'
import type {
  ContaminationTeamRead,
  HazardTeam,
} from '@/modules/contamination-team/models/contaminationTeam'
import {
  fetchResponseRoster,
  updateResponseTeamPlace,
} from '../services/responseStationService'

export const useResponseStationStore = defineStore('responseStation', () => {
  const roster = ref<ContaminationTeamRead | null>(null)
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const busyDwellerIds = ref<string[]>([])
  // Every load supersedes the previous one; a response only lands when it
  // belongs to the latest vault/token pair that was asked for.
  let loadVersion = 0

  function reset(): void {
    loadVersion++
    roster.value = null
    isLoading.value = false
    error.value = null
  }

  async function loadRoster(vaultId: string, token: string): Promise<void> {
    const version = ++loadVersion
    error.value = null
    if (!vaultId || !token) {
      isLoading.value = false
      return
    }
    isLoading.value = true
    try {
      const updated = await fetchResponseRoster(vaultId, token)
      if (version !== loadVersion) return
      roster.value = updated.vault_id === vaultId ? updated : null
    } catch (caught) {
      if (version !== loadVersion) return
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
    active: boolean,
    token: string
  ): Promise<void> {
    if (!vaultId || !token || isLoading.value || busyDwellerIds.value.length > 0) return
    const version = loadVersion
    busyDwellerIds.value = [...busyDwellerIds.value, dwellerId]
    try {
      const updated = await updateResponseTeamPlace(vaultId, team, dwellerId, active, token)
      if (updated && version === loadVersion) roster.value = updated
    } catch (caught) {
      handleStoreError(caught, 'Failed to update response team')
    } finally {
      busyDwellerIds.value = busyDwellerIds.value.filter((id) => id !== dwellerId)
    }
  }

  return { roster, isLoading, error, busyDwellerIds, loadRoster, setPlace, reset }
})
