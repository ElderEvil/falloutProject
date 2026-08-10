import { ref, computed } from 'vue'
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
        const gen = _pollGeneration
        const vaultId = _pollVaultId.value
        const token = _pollToken.value
        try {
          const data = await mapService.getVaultMap(token, vaultId)
          if (gen !== _pollGeneration || vaultId !== _pollVaultId.value) return
          locations.value = data.locations
          vaultMarkers.value = data.vault_markers
        } catch (err) {
          if (gen !== _pollGeneration || vaultId !== _pollVaultId.value) return
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
  let _pollGeneration = 0

  // Getters
  const unlockedPlacesCount = computed(
    () => locations.value.filter((loc) => loc.is_unlocked).length
  )

  // Actions
  async function fetchMap(vaultId: string, token: string): Promise<void> {
    const gen = ++_pollGeneration
    isLoading.value = true
    error.value = null
    try {
      const data = await mapService.getVaultMap(token, vaultId)
      if (gen !== _pollGeneration) return
      locations.value = data.locations
      vaultMarkers.value = data.vault_markers
    } catch (err) {
      if (gen !== _pollGeneration) return
      handleStoreError(err, 'Failed to fetch map')
      error.value = 'Failed to load map'
    } finally {
      if (gen === _pollGeneration) {
        isLoading.value = false
      }
    }
  }

  function startPolling(vaultId: string, token: string): void {
    _pollVaultId.value = vaultId
    _pollToken.value = token
    _pollGeneration += 1
    if (!isPollingActive.value) {
      resumePolling()
    }
  }

  function stopPolling(): void {
    _pollVaultId.value = null
    _pollToken.value = null
    _pollGeneration += 1
    if (isPollingActive.value) {
      pausePolling()
    }
  }

  async function refreshMap(vaultId: string, token?: string): Promise<void> {
    const effectiveToken = token ?? _pollToken.value
    if (!effectiveToken) return
    const gen = _pollGeneration
    try {
      const data = await mapService.getVaultMap(effectiveToken, vaultId)
      if (gen !== _pollGeneration) return
      locations.value = data.locations
      vaultMarkers.value = data.vault_markers
    } catch (err) {
      if (gen !== _pollGeneration) return
      error.value = handleStoreError(err, 'Failed to refresh map after chat')
    }
  }

  return {
    // State
    locations,
    vaultMarkers,
    isLoading,
    error,
    // Getters
    unlockedPlacesCount,
    // Actions
    fetchMap,
    refreshMap,
    startPolling,
    stopPolling,
  }
})
