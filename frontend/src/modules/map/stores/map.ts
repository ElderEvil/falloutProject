import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { useIntervalFn, useLocalStorage } from '@vueuse/core'
import type {
  DiscoveryRouteRead,
  ExpeditionSiteMarkerRead,
  PlaceGroup,
  PlayerVaultMarkerRead,
  VaultMapResponse,
  VaultMarkerRead,
  WastelandLocationWithDwellers,
} from '../models/map'
import * as mapService from '../services/mapService'
import { computeExploredMask } from '../utils/fog'
import { isKnownLocation } from '../utils/visibility'
import { handleStoreError } from '@/core/utils/errorHandler'
import { useToast } from '@/core/composables/useToast'

export const VIEWED_LOCATIONS_STORAGE_KEY = 'map:viewed-location-keys'

export const useMapStore = defineStore('map', () => {
  // State
  const locations = ref<WastelandLocationWithDwellers[]>([])
  const vaultMarkers = ref<VaultMarkerRead[]>([])
  const playerVaults = ref<PlayerVaultMarkerRead[]>([])
  const discoveryRoutes = ref<DiscoveryRouteRead[]>([])
  const expeditionSites = ref<ExpeditionSiteMarkerRead[]>([])
  const placeGroups = ref<PlaceGroup[]>([])
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
          applyMapData(data)
          notifyNewUnlocks(data, vaultId)
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
  const placeGroupByKey = computed(() => new Map(placeGroups.value.map((group) => [group.key, group])))

  // Derived fog of war mask (single source; shared by the render layer and any
  // interaction that needs to test whether a cell is explored).
  const exploredMask = computed(() =>
    computeExploredMask({
      home: locations.value.find((loc) => loc.type === 'home_vault') ?? null,
      discovered: locations.value.filter(isKnownLocation),
      trailPoints: discoveryRoutes.value.flatMap((route) => route.points),
    })
  )

  function isUnseenDiscovery(loc: WastelandLocationWithDwellers): boolean {
    return (
      loc.type === 'discovery' &&
      isKnownLocation(loc) &&
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
  const toast = useToast()
  const prevUnlockedByVault = ref<Record<string, string[]>>({})

  function applyMapData(data: VaultMapResponse): void {
    locations.value = data.locations
    vaultMarkers.value = data.vault_markers
    playerVaults.value = data.player_vaults ?? []
    discoveryRoutes.value = data.discovery_routes ?? []
    expeditionSites.value = data.expedition_sites ?? []
    placeGroups.value = data.place_groups ?? []
  }

  // Single unlock toast per vault: baseline load stays silent, repeats stay silent.
  function notifyNewUnlocks(data: VaultMapResponse, vaultId: string): void {
    const current = data.locations.filter(isKnownLocation).map((l) => l.id)
    const prev = prevUnlockedByVault.value[vaultId]
    prevUnlockedByVault.value[vaultId] = current
    if (prev === undefined) return
    const fresh = current.filter((id) => !prev.includes(id))
    if (fresh.length === 0) return
    if (fresh.length === 1) {
      const name = data.locations.find((l) => l.id === fresh[0])?.name ?? 'a new location'
      toast.success(`New discovery: ${name}`)
    } else {
      toast.success(`${fresh.length} new discoveries on the map`)
    }
  }

  // Always fetch the full map (never unlocked_only): locked previews and
  // deep-links need locked rows; visibility is enforced client-side.
  async function fetchMap(vaultId: string, token: string): Promise<void> {
    const gen = ++_pollGeneration
    isLoading.value = true
    error.value = null
    try {
      const data = await mapService.getVaultMap(token, vaultId)
      if (gen !== _pollGeneration) return
      applyMapData(data)
      notifyNewUnlocks(data, vaultId)
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
      applyMapData(data)
      notifyNewUnlocks(data, vaultId)
    } catch (err) {
      if (gen !== _pollGeneration) return
      error.value = handleStoreError(err, 'Failed to refresh map after chat')
    }
  }

  return {
    locations,
    vaultMarkers,
    playerVaults,
    discoveryRoutes,
    expeditionSites,
    placeGroups,
    placeGroupByKey,
    exploredMask,
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
