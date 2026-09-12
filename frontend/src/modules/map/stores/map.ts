import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { useIntervalFn, useLocalStorage } from '@vueuse/core'
import type {
  DiscoveryRouteRead,
  WastelandLocationWithDwellers,
  VaultMarkerRead,
} from '../models/map'
import * as mapService from '../services/mapService'
import { handleStoreError } from '@/core/utils/errorHandler'

export const VIEWED_LOCATIONS_STORAGE_KEY = 'map:viewed-location-keys'

export const useMapStore = defineStore('map', () => {
  // State
  const locations = ref<WastelandLocationWithDwellers[]>([])
  const vaultMarkers = ref<VaultMarkerRead[]>([])
  const discoveryRoutes = ref<DiscoveryRouteRead[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const viewedLocationKeys = useLocalStorage<Set<string>>(
    VIEWED_LOCATIONS_STORAGE_KEY,
    new Set(),
    {
      serializer: {
        read: (raw) => new Set<string>(JSON.parse(raw) as string[]),
        write: (value) => JSON.stringify([...value]),
      },
    }
  )

  const viewedKey = (vaultId: string, locationId: string) => `${vaultId}:${locationId}`

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
          discoveryRoutes.value = data.discovery_routes ?? []
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
  const hasUnseenDiscoveries = computed(() => locations.value.some(isUnseenDiscovery))

  function isUnseenDiscovery(loc: WastelandLocationWithDwellers): boolean {
    return (
      loc.type === 'discovery' &&
      loc.is_unlocked !== false &&
      !viewedLocationKeys.value.has(viewedKey(loc.vault_id, loc.id))
    )
  }

  function markLocationViewed(vaultId: string, locationId: string): void {
    const key = viewedKey(vaultId, locationId)
    if (!viewedLocationKeys.value.has(key)) {
      viewedLocationKeys.value = new Set(viewedLocationKeys.value).add(key)
    }
  }

  function isLocationViewed(vaultId: string, locationId: string): boolean {
    return viewedLocationKeys.value.has(viewedKey(vaultId, locationId))
  }

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
      discoveryRoutes.value = data.discovery_routes ?? []
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
      discoveryRoutes.value = data.discovery_routes ?? []
    } catch (err) {
      if (gen !== _pollGeneration) return
      error.value = handleStoreError(err, 'Failed to refresh map after chat')
    }
  }

  return {
    locations,
    vaultMarkers,
    discoveryRoutes,
    isLoading,
    error,
    viewedLocationKeys,
    hasUnseenDiscoveries,
    isUnseenDiscovery,
    markLocationViewed,
    isLocationViewed,
    fetchMap,
    refreshMap,
    startPolling,
    stopPolling,
  }
})
