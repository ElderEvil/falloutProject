<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useMapStore } from '../stores/map'
import { useExplorationStore } from '@/modules/exploration/stores/exploration'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { isMature, type DwellerShort } from '@/modules/dwellers/models/dweller'
import { useToast } from '@/core/composables/useToast'
import { getErrorMessage } from '@/core/utils/errorHandler'
import SidePanel from '@/core/components/common/SidePanel.vue'
import PageContentRail from '@/core/components/common/PageContentRail.vue'
import PageHeader from '@/core/components/common/PageHeader.vue'
import { Skeleton } from '@/core/components/ui/skeleton'
import { Button } from '@/core/components/ui/button'
import WorldMap from '../components/WorldMap.vue'
import MarkerDetailModal from '../components/MarkerDetailModal.vue'
import { useSidePanel } from '@/core/composables/useSidePanel'
import type {
  ExpeditionSiteMarkerRead,
  ExplorerTrack,
  WastelandLocationWithDwellers,
  VaultMarkerRead,
} from '../models/map'
import { buildExplorerTracks } from '../utils/explorerTracks'

const authStore = useAuthStore()
const mapStore = useMapStore()
const explorationStore = useExplorationStore()
const { filter: dwellerStore } = useDwellerStore()
const vaultStore = useVaultStore()
const route = useRoute()
const router = useRouter()
const { isCollapsed } = useSidePanel()
const toast = useToast()

const vaultId = computed(() => route.params.id as string)

// Modal state
const showModal = ref(false)
// Single selection identity; selected objects derive from store state so polling
// refreshes them automatically instead of manual re-selection after each refresh.
const selectedMarkerId = ref<string | null>(null)
const selectedLocation = computed<WastelandLocationWithDwellers | null>(() => {
  const id = selectedMarkerId.value
  if (id === null || !id.startsWith('loc-')) return null
  return mapStore.locations.find((l) => l.id === id.slice(4)) ?? null
})
const selectedVaultMarker = computed<VaultMarkerRead | null>(() => {
  const id = selectedMarkerId.value
  if (id === null || !id.startsWith('vault-')) return null
  return mapStore.vaultMarkers.find((m) => m.name === id.slice(6)) ?? null
})
const selectedSite = computed<ExpeditionSiteMarkerRead | null>(() => {
  const id = selectedMarkerId.value
  if (id === null || !id.startsWith('site-')) return null
  return mapStore.expeditionSites.find((s) => s.id === id.slice(5)) ?? null
})

// Explorer tracking: active runs projected onto the map. Dispatched runs mark
// their target location; free-roam runs surface at the last discovery point.
const dwellerNames = computed(() => {
  const names = new Map<string, string>()
  for (const dweller of dwellerStore.dwellers) {
    if (!dweller.first_name) continue
    names.set(dweller.id, `${dweller.first_name} ${dweller.last_name ?? ''}`.trim())
  }
  return names
})

// Explorer markers show the dweller's thumbnail when the vault roster has one;
// otherwise the map falls back to the walking icon.
const dwellerThumbnails = computed(() => {
  const thumbnails = new Map<string, string | null>()
  for (const dweller of dwellerStore.dwellers) {
    thumbnails.set(dweller.id, dweller.thumbnail_url ?? null)
  }
  return thumbnails
})

const explorerTracks = computed<ExplorerTrack[]>(() =>
  buildExplorerTracks(
    // The store can still hold the previous vault's active runs after a vault
    // switch; target_location_id references shared WorldLocation rows, so a
    // stale run could match a location on the new map. Scope to this vault.
    explorationStore.explorations.filter((e) => e.vault_id === vaultId.value),
    mapStore.discoveryRoutes,
    dwellerNames.value,
    dwellerThumbnails.value
  )
)

// Dispatch state (issue 772). The team menu now lives inside the location
// details modal; the map only preloads its data and routes the confirm.
// Blocks repeated Dispatch confirms while the request is in flight.
const isDispatching = ref(false)
// True while the vault record / dweller roster feeding the in-modal Send-team
// section loads, so the modal's confirm stays disabled until supplies are real.
const isPreparingDispatch = ref(false)

async function ensureDispatchData() {
  const requestedVaultId = vaultId.value
  const token = authStore.token
  if (!requestedVaultId || !token) return
  isPreparingDispatch.value = true
  try {
    // The shell hydrates loadedVaults asynchronously; showing the Send-team
    // section before that lands renders the supply sliders as zeros. Load the
    // vault record, then the roster, and let a failure leave supplies at zero.
    await vaultStore.ensureVaultLoaded(requestedVaultId, token)
    // A route change mid-load means this data no longer belongs to the view.
    if (vaultId.value !== requestedVaultId || authStore.token !== token) return
    if (dwellerStore.dwellers.length === 0) {
      await dwellerStore.fetchDwellersByVault(requestedVaultId, token)
    }
  } catch {
    // Unloadable vault: the section still renders, supplies just stay at zero.
  } finally {
    isPreparingDispatch.value = false
  }
}

async function handleDispatch(payload: {
  dwellerIds: string[]
  supplies: { stimpaks: number; radaways: number }
}) {
  const location = selectedLocation.value
  if (
    isDispatching.value ||
    !location ||
    payload.dwellerIds.length === 0 ||
    !vaultId.value ||
    !authStore.token
  )
    return
  isDispatching.value = true
  try {
    await explorationStore.dispatchToLocation(
      vaultId.value,
      payload.dwellerIds,
      location.id,
      payload.supplies
    )
    showModal.value = false
    await mapStore.refreshMap(vaultId.value, authStore.token)
    toast.success(`${location.name} — dispatch sent`)
  } catch (err) {
    toast.error(getErrorMessage(err))
  } finally {
    isDispatching.value = false
  }
}

// Admin debug tool: reveal the whole atlas by dropping the fog layer.
const fogDisabled = ref(false)

const vaultMedicalSupplies = computed(() => {
  const vault = vaultId.value ? vaultStore.loadedVaults[vaultId.value] : null
  return { stimpaks: vault?.stimpack ?? 0, radaways: vault?.radaway ?? 0 }
})

// Dwellers already out (active or returning) cannot be sent again; the details
// modal's dispatch picker only offers eligible, mature candidates.
const departingDwellerIds = computed(
  () =>
    new Set(
      explorationStore.explorations
        .filter(
          (exploration) =>
            exploration.vault_id === vaultId.value &&
            (exploration.status === 'active' || exploration.status === 'returning'),
        )
        .map((exploration) => exploration.dweller_id),
    ),
)

// Mirror the backend availability policy (app/utils/dweller_availability): a
// dweller is unavailable when dead or already out (exploring/questing). The
// status check keeps this correct even when the exploration store is empty or
// stale, which the loaded-records set alone cannot cover. A dead dweller carries
// the `dead` status, so listing it here covers `is_dead` too.
const UNAVAILABLE_DEPARTURE_STATUSES = new Set(['exploring', 'questing', 'dead'])

function isAvailableForDeparture(dweller: DwellerShort): boolean {
  return (
    isMature(dweller) &&
    !UNAVAILABLE_DEPARTURE_STATUSES.has(dweller.status) &&
    !departingDwellerIds.value.has(dweller.id)
  )
}

const departureCandidates = computed(() => dwellerStore.dwellers.filter(isAvailableForDeparture))

function isDirectDispatchable(loc: WastelandLocationWithDwellers): boolean {
  const clearState = loc.clear_state
  return !!clearState?.clearable && (!clearState.cleared || clearState.time_remaining_seconds <= 0)
}

function handleMarkerClick(
  payload:
    | { kind: 'location'; data: WastelandLocationWithDwellers }
    | { kind: 'vault'; data: VaultMarkerRead }
    | { kind: 'site'; data: ExpeditionSiteMarkerRead }
) {
  if (payload.kind === 'location') {
    selectedMarkerId.value = `loc-${payload.data.id}`
    mapStore.markLocationViewed(payload.data.vault_id, payload.data.id)
    // Symmetric deep-link: a clicked marker owns ?place= so the URL is
    // shareable and survives reload; the ?place= watcher opens the modal.
    if (route.query.place !== payload.data.id) {
      void router.push({ query: { ...route.query, place: payload.data.id } })
    }
    // Team dispatch now lives in the details modal; preload the vault supplies
    // and roster so its Send-team section is usable when it opens.
    if (isDirectDispatchable(payload.data)) void ensureDispatchData()
  } else if (payload.kind === 'site') {
    selectedMarkerId.value = `site-${payload.data.id}`
    clearPlaceQuery()
  } else {
    selectedMarkerId.value = `vault-${payload.data.name}`
    clearPlaceQuery()
  }
  showModal.value = true
}

async function loadMap() {
  if (!authStore.isAuthenticated || !vaultId.value) return
  const token = authStore.token as string
  mapStore.stopPolling()
  // Snapshot first: terrain needs no vault context and is version-pinned, so it
  // loads independently of (and is never refetched by) the vault-map poll loop.
  await Promise.all([mapStore.fetchWorldSnapshot(token), mapStore.fetchMap(vaultId.value, token)])
  mapStore.startPolling(vaultId.value, token)
  tryOpenPlaceFromQuery()
}

function tryOpenPlaceFromQuery() {
  const placeId = route.query.place
  if (typeof placeId !== 'string' || !placeId) return
  // Loop guard: the click handler writes ?place=, which re-fires this watcher.
  if (showModal.value && selectedLocation.value?.id === placeId) return
  const loc = mapStore.locations.find((l) => l.id === placeId)
  if (loc) {
    handleMarkerClick({ kind: 'location', data: loc })
  }
}

function clearPlaceQuery() {
  if (route.query.place === undefined) return
  const query = { ...route.query }
  delete query.place
  void router.replace({ query })
}

watch(
  vaultId,
  () => {
    loadMap()
  },
  { immediate: true }
)

// Open marker detail if ?place= query param changes while map is already loaded
watch(
  () => route.query.place,
  () => {
    tryOpenPlaceFromQuery()
  }
)

// Explorer tracking rides the existing 30s map poll: every poll replaces the
// locations array, so this watcher re-syncs active explorations (targets and
// discovery trails) without any new polling or SSE wiring.
watch(
  () => mapStore.locations,
  () => {
    if (vaultId.value && authStore.token) {
      explorationStore.fetchExplorationsByVault(vaultId.value, authStore.token).catch(() => {})
    }
  }
)

// Closing the modal releases ?place= so a dismissed location never reopens on reload.
watch(showModal, (open) => {
  if (!open) clearPlaceQuery()
})

onUnmounted(() => {
  mapStore.stopPolling()
})

function retry() {
  loadMap()
}

const hasNoData = computed(
  () => !mapStore.isLoading && mapStore.locations.length === 0 && mapStore.vaultMarkers.length === 0
)
</script>

<template>
  <div class="relative min-h-screen bg-terminal-background font-mono text-terminal-green">
    <div class="vault-layout">
      <!-- Side Panel -->
      <SidePanel />

      <!-- Main Content Area -->
      <div class="main-content flicker" :class="{ collapsed: isCollapsed }">
        <PageContentRail>
          <PageHeader
            title="World Map"
            icon="mdi:map"
            subtitle="Track discoveries, expeditions & the wider wasteland."
          />

          <!-- Loading skeleton -->
          <div v-if="mapStore.isLoading" class="map-skeleton">
            <Skeleton class="h-(--map-pane-size) w-full rounded-lg" />
          </div>

          <!-- Error state -->
          <div v-else-if="mapStore.error" class="empty-state">
            <p class="empty-text terminal-glow-subtle">{{ mapStore.error }}</p>
            <Button
              variant="outline"
              size="sm"
              class="mt-4 border-2 border-theme-primary bg-transparent"
              @click="retry"
            >
              Retry
            </Button>
          </div>

          <!-- Empty state -->
          <div v-else-if="hasNoData" class="empty-state">
            <p class="empty-text terminal-glow-subtle">
              The wasteland is uncharted. Recruit dwellers and send explorers to fill the map.
            </p>
            <Button
              variant="outline"
              size="sm"
              class="mt-4 border-2 border-theme-primary bg-transparent"
              @click="$router.push(`/vault/${vaultId}`)"
            >
              Recruit Dwellers
            </Button>
          </div>

          <!-- Map -->
          <WorldMap
            v-else
            :locations="mapStore.locations"
            :vault-markers="mapStore.vaultMarkers"
            :player-vaults="mapStore.playerVaults"
            :discovery-routes="mapStore.discoveryRoutes"
            :expedition-sites="mapStore.expeditionSites"
            :explorer-tracks="explorerTracks"
            :fog-disabled="fogDisabled"
            :selected-marker-id="selectedMarkerId"
            @update:selected-marker-id="selectedMarkerId = $event"
            @marker-click="handleMarkerClick"
          />

          <!-- Admin debug: lift the fog to inspect the whole atlas -->
          <div v-if="authStore.isSuperuser" class="map-toolbar">
            <Button variant="outline" size="sm" @click="fogDisabled = !fogDisabled">
              {{ fogDisabled ? 'Restore fog' : 'Remove fog (debug)' }}
            </Button>
          </div>

          <!-- Detail modal: also hosts the team dispatch menu for clearable points -->
          <MarkerDetailModal
            v-model="showModal"
            :location="selectedLocation"
            :vault-marker="selectedVaultMarker"
            :site="selectedSite"
            :dwellers="departureCandidates"
            :max-party-size="3"
            :max-stimpaks="vaultMedicalSupplies.stimpaks"
            :max-radaways="vaultMedicalSupplies.radaways"
            :supplies-loading="isPreparingDispatch"
            @dispatch="handleDispatch"
          />

        </PageContentRail>
      </div>
    </div>
  </div>
</template>

<style scoped>
.map-toolbar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-top: 0.75rem;
}

.vault-layout {
  display: flex;
  min-height: 100vh;
}

.main-content {
  flex: 1;
  margin-left: 240px;
  transition: margin-left 0.3s ease;
  font-weight: 700;
  letter-spacing: 0.025em;
  line-height: 1.6;
}

.main-content.collapsed {
  margin-left: 64px;
}

.main-content p,
.main-content span,
.main-content div {
  text-shadow: 0 0 2px var(--color-theme-glow);
}

.map-skeleton {
  width: 100%;
}

.empty-state {
  max-width: 800px;
  padding: 4rem 2rem;
  text-align: center;
}

.empty-text {
  color: var(--color-theme-primary);
  font-size: var(--font-size-lg);
  opacity: 0.7;
}
</style>
