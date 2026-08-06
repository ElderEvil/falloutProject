import { ref } from 'vue'
import { defineStore } from 'pinia'
import { useIntervalFn } from '@vueuse/core'
import type { WastelandLocationWithDwellers, VaultMarkerRead } from '../models/map'
import * as mapService from '../services/mapService'
import { handleStoreError } from '@/core/utils/errorHandler'

export const useMapStore = defineStore('map', () => {
  // State
  const locations = ref<WastelandLocationWithDwellers[]>([])
  const vaultMarkers = ref<VaultMarkerRead[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  // Polling control (30s interval per plan D13)
  const {
    pause: pausePolling,
    resume: resumePolling,
    isActive: isPollingActive,
  } = useIntervalFn(
    async () => {
      if (_pollVaultId.value && _pollToken.value) {
        try {
          const data = await mapService.getVaultMap(_pollToken.value, _pollVaultId.value)
          locations.value = data.locations
          vaultMarkers.value = data.vault_markers
        } catch (err) {
          handleStoreError(err, 'Failed to poll map')
        }
      }
    },
    30000,
    { immediate: false }
  )

  // Internal refs for polling context
  const _pollVaultId = ref<string | null>(null)
  const _pollToken = ref<string | null>(null)

  // Actions
  async function fetchMap(vaultId: string, token: string): Promise<void> {
    isLoading.value = true
    error.value = null
    try {
      const data = await mapService.getVaultMap(token, vaultId)
      locations.value = data.locations
      vaultMarkers.value = data.vault_markers
    } catch (err) {
      handleStoreError(err, 'Failed to fetch map')
      error.value = 'Failed to load map'
    } finally {
      isLoading.value = false
    }
  }

  function startPolling(vaultId: string, token: string): void {
    _pollVaultId.value = vaultId
    _pollToken.value = token
    if (!isPollingActive.value) {
      resumePolling()
    }
  }

  function stopPolling(): void {
    _pollVaultId.value = null
    _pollToken.value = null
    if (isPollingActive.value) {
      pausePolling()
    }
  }

  return {
    // State
    locations,
    vaultMarkers,
    isLoading,
    error,
    // Actions
    fetchMap,
    startPolling,
    stopPolling,
  }
})
