import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { useLocalStorage } from '@vueuse/core'
import { usePolling } from '@/core/composables/usePolling'
import type {
  CollectibleSetProgressRead,
  DiscoveryRouteRead,
  CombatZoneMarkerRead,
  ExpeditionSiteMarkerRead,
  PlaceGroup,
  PlayerVaultMarkerRead,
  VaultMapResponse,
  VaultMarkerRead,
  WastelandLocationWithDwellers,
  WorldSnapshotRead,
} from '../models/map'
import * as mapService from '../services/mapService'
import { isKnownLocation } from '../utils/visibility'
import { handleStoreError } from '@/core/utils/errorHandler'
import { useToast } from '@/core/composables/useToast'
import { useAuthStore } from '@/modules/auth/stores/auth'

export const VIEWED_LOCATIONS_STORAGE_KEY = 'map:viewed-location-keys'

export const useMapStore = defineStore('map', () => {
  const authStore = useAuthStore()
  // State
  const locations = ref<WastelandLocationWithDwellers[]>([])
  const vaultMarkers = ref<VaultMarkerRead[]>([])
  const playerVaults = ref<PlayerVaultMarkerRead[]>([])
  const discoveryRoutes = ref<DiscoveryRouteRead[]>([])
  const expeditionSites = ref<ExpeditionSiteMarkerRead[]>([])
  const combatZone = ref<CombatZoneMarkerRead | null>(null)
  const placeGroups = ref<PlaceGroup[]>([])
  // The vault whose rows the state above currently holds. A load for another vault clears
  // it first, so a slow or failed switch cannot render the previous vault's map under the
  // new one; a refresh of the same vault keeps its rows on screen.
  const loadedVaultId = ref<string | null>(null)
  // Set progress ships with the map payload; the map surfaces it because collectibles are found
  // at these sites. Empty while the feature ships dark, and until the first load.
  const collectibleSets = ref<CollectibleSetProgressRead[]>([])
  // Backend-owned world snapshot (terrain + slots). Fetched once per map load:
  // the snapshot is immutable per (world_id, generator_version), so polling the
  // vault map never refetches it. Null until loaded — terrain renders nothing
  // rather than falling back to local generation.
  const worldSnapshot = ref<WorldSnapshotRead | null>(null)
  const snapshotError = ref<string | null>(null)
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const viewedLocationKeys = useLocalStorage<Set<string>>(VIEWED_LOCATIONS_STORAGE_KEY, new Set(), {
    serializer: {
      read: (raw) => new Set<string>(JSON.parse(raw) as string[]),
      write: (value) => JSON.stringify([...value]),
    },
  })

  const viewedKey = (vaultId: string, locationId: string) => `${vaultId}:${locationId}`

  // Polling control (30s interval per plan D13)
  const {
    pause: pausePolling,
    resume: resumePolling,
    isActive: isPollingActive,
  } = usePolling(
    async () => {
      if (_pollVaultId.value) {
        const gen = _pollGeneration
        const vaultId = _pollVaultId.value
        const session = authStore.sessionGeneration
        prepareVaultLoad(vaultId)
        try {
          const data = await mapService.getVaultMap(vaultId)
          if (
            gen !== _pollGeneration ||
            vaultId !== _pollVaultId.value ||
            session !== authStore.sessionGeneration
          )
            return
          applyMapData(data)
          notifyNewUnlocks(data, vaultId)
        } catch (err) {
          if (
            gen !== _pollGeneration ||
            vaultId !== _pollVaultId.value ||
            session !== authStore.sessionGeneration
          )
            return
          throw err
        }
      }
    },
    { interval: 30000, immediate: false }
  )

  pausePolling()

  // Internal refs for polling context
  const _pollVaultId = ref<string | null>(null)
  let _pollGeneration = 0

  // Getters
  const hasUnseenDiscoveries = computed(() => locations.value.some(isUnseenDiscovery))
  const placeGroupByKey = computed(
    () => new Map(placeGroups.value.map((group) => [group.key, group]))
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
    combatZone.value = data.combat_zone ?? null
    placeGroups.value = data.place_groups ?? []
    collectibleSets.value = data.collectible_sets ?? []
  }

  // A vault switch must not show the previous vault's rows while the new load is in flight,
  // or keep them if it fails. Everything applyMapData fills is vault-scoped, so clear it together.
  function prepareVaultLoad(vaultId: string): void {
    if (loadedVaultId.value !== null && loadedVaultId.value !== vaultId) {
      locations.value = []
      vaultMarkers.value = []
      playerVaults.value = []
      discoveryRoutes.value = []
      expeditionSites.value = []
      placeGroups.value = []
      collectibleSets.value = []
    }
    loadedVaultId.value = vaultId
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
  async function fetchMap(vaultId: string): Promise<void> {
    const gen = ++_pollGeneration
    const session = authStore.sessionGeneration
    prepareVaultLoad(vaultId)
    isLoading.value = true
    error.value = null
    try {
      const data = await mapService.getVaultMap(vaultId)
      if (gen !== _pollGeneration || session !== authStore.sessionGeneration) return
      applyMapData(data)
      notifyNewUnlocks(data, vaultId)
    } catch (err) {
      if (gen !== _pollGeneration || session !== authStore.sessionGeneration) return
      handleStoreError(err, 'Failed to fetch map')
      error.value = 'Failed to load map'
    } finally {
      if (gen === _pollGeneration) {
        isLoading.value = false
      }
    }
  }

  function startPolling(vaultId: string): void {
    _pollVaultId.value = vaultId
    _pollGeneration += 1
    if (!isPollingActive.value) {
      resumePolling()
    }
  }

  function stopPolling(): void {
    _pollVaultId.value = null
    _pollGeneration += 1
    pausePolling()
  }

  async function fetchWorldSnapshot(): Promise<void> {
    snapshotError.value = null
    const session = authStore.sessionGeneration
    try {
      const snapshot = await mapService.getWorldSnapshot()
      if (session !== authStore.sessionGeneration) return
      if (snapshot.terrain.length !== snapshot.width * snapshot.height) {
        throw new Error(
          `Snapshot terrain has ${snapshot.terrain.length} cells for a ${snapshot.width}x${snapshot.height} grid`
        )
      }
      if (snapshot.width !== snapshot.height) {
        throw new Error(
          `Snapshot grid is ${snapshot.width}x${snapshot.height}: only square grids are supported`
        )
      }
      worldSnapshot.value = snapshot
    } catch (err) {
      if (session !== authStore.sessionGeneration) return
      worldSnapshot.value = null
      snapshotError.value = handleStoreError(
        err,
        'World terrain unavailable — showing markers only'
      )
      // Visible, non-blocking: markers/routes/fog still render over the empty
      // terrain rather than failing the whole map load.
    }
  }

  async function refreshMap(vaultId: string): Promise<void> {
    if (!authStore.isAuthenticated) return
    const gen = _pollGeneration
    const session = authStore.sessionGeneration
    prepareVaultLoad(vaultId)
    try {
      const data = await mapService.getVaultMap(vaultId)
      if (gen !== _pollGeneration || session !== authStore.sessionGeneration) return
      applyMapData(data)
      notifyNewUnlocks(data, vaultId)
    } catch (err) {
      if (gen !== _pollGeneration || session !== authStore.sessionGeneration) return
      error.value = handleStoreError(err, 'Failed to refresh map after chat')
    }
  }

  return {
    locations,
    vaultMarkers,
    playerVaults,
    discoveryRoutes,
    expeditionSites,
    combatZone,
    placeGroups,
    placeGroupByKey,
    collectibleSets,
    isLoading,
    error,
    viewedLocationKeys,
    hasUnseenDiscoveries,
    isUnseenDiscovery,
    markLocationViewed,
    isLocationViewed,
    fetchMap,
    refreshMap,
    worldSnapshot,
    snapshotError,
    fetchWorldSnapshot,
    startPolling,
    stopPolling,
  }
})
