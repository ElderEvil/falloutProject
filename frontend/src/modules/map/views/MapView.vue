<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useMapStore } from '../stores/map'
import { useExplorationStore } from '@/modules/exploration/stores/exploration'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useToast } from '@/core/composables/useToast'
import { getErrorMessage } from '@/core/utils/errorHandler'
import SidePanel from '@/core/components/common/SidePanel.vue'
import PageContentRail from '@/core/components/common/PageContentRail.vue'
import PageHeader from '@/core/components/common/PageHeader.vue'
import { Skeleton } from '@/core/components/ui/skeleton'
import { Button } from '@/core/components/ui/button'
import WorldMap from '../components/WorldMap.vue'
import MarkerDetailModal from '../components/MarkerDetailModal.vue'
import PartySelectionModal from '@/modules/progression/components/PartySelectionModal.vue'
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
const route = useRoute()
const router = useRouter()
const { isCollapsed } = useSidePanel()
const toast = useToast()

const vaultId = computed(() => route.params.id as string)

// Modal state
const showModal = ref(false)
const selectedLocation = ref<WastelandLocationWithDwellers | null>(null)
const selectedVaultMarker = ref<VaultMarkerRead | null>(null)
const selectedSite = ref<ExpeditionSiteMarkerRead | null>(null)

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

const explorerTracks = computed<ExplorerTrack[]>(() =>
  buildExplorerTracks(explorationStore.explorations, mapStore.discoveryRoutes, dwellerNames.value)
)

// Dispatch picker state (issue 772, phase 4b)
const showDispatchModal = ref(false)
const dispatchLocation = ref<WastelandLocationWithDwellers | null>(null)
// Blocks repeated Dispatch confirms while the request is in flight.
const isDispatching = ref(false)

function handleDispatchRequest() {
  if (selectedLocation.value) void openDispatchPicker(selectedLocation.value)
}

async function openDispatchPicker(location: WastelandLocationWithDwellers) {
  dispatchLocation.value = location
  showDispatchModal.value = true
  if (vaultId.value && authStore.token && dwellerStore.dwellers.length === 0) {
    await dwellerStore.fetchDwellersByVault(vaultId.value, authStore.token)
  }
}

async function handleDispatch(dwellerIds: string[]) {
  const location = dispatchLocation.value
  if (
    isDispatching.value ||
    !location ||
    dwellerIds.length === 0 ||
    !vaultId.value ||
    !authStore.token
  )
    return
  isDispatching.value = true
  try {
    await explorationStore.dispatchToLocation(vaultId.value, dwellerIds, location.id)
    showDispatchModal.value = false
    dispatchLocation.value = null
    await mapStore.refreshMap(vaultId.value, authStore.token)
    const refreshed = mapStore.locations.find((l) => l.id === location.id)
    if (refreshed) selectedLocation.value = refreshed
    toast.success(`${location.name} — dispatch sent`)
  } catch (err) {
    toast.error(getErrorMessage(err))
  } finally {
    isDispatching.value = false
  }
}

function handleMarkerClick(
  payload:
    | { kind: 'location'; data: WastelandLocationWithDwellers }
    | { kind: 'vault'; data: VaultMarkerRead }
    | { kind: 'site'; data: ExpeditionSiteMarkerRead }
) {
  if (payload.kind === 'location') {
    selectedLocation.value = payload.data
    selectedVaultMarker.value = null
    selectedSite.value = null
    mapStore.markLocationViewed(payload.data.vault_id, payload.data.id)
    // Symmetric deep-link: a clicked marker owns ?place= so the URL is
    // shareable and survives reload; the ?place= watcher opens the modal.
    if (route.query.place !== payload.data.id) {
      void router.push({ query: { ...route.query, place: payload.data.id } })
    }
  } else if (payload.kind === 'site') {
    selectedLocation.value = null
    selectedVaultMarker.value = null
    selectedSite.value = payload.data
    clearPlaceQuery()
  } else {
    selectedLocation.value = null
    selectedVaultMarker.value = payload.data
    selectedSite.value = null
    clearPlaceQuery()
  }
  showModal.value = true
}

async function loadMap() {
  if (!authStore.isAuthenticated || !vaultId.value) return
  const token = authStore.token as string
  mapStore.stopPolling()
  await mapStore.fetchMap(vaultId.value, token)
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

const mapPaneSize = 'min(var(--map-pane-size), calc(100vw - 2rem))'
const mapPaneHeight = 'var(--map-pane-size)'
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
            <Skeleton :style="{ width: mapPaneSize, height: mapPaneSize }" class="rounded-lg" />
            <Skeleton :style="{ width: '100%', height: mapPaneHeight }" class="rounded-lg" />
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
            :discovery-routes="mapStore.discoveryRoutes"
            :expedition-sites="mapStore.expeditionSites"
            :explorer-tracks="explorerTracks"
            @marker-click="handleMarkerClick"
          />

          <!-- Detail modal -->
          <MarkerDetailModal
            v-model="showModal"
            :location="selectedLocation"
            :vault-marker="selectedVaultMarker"
            :site="selectedSite"
            @dispatch="handleDispatchRequest"
          />

          <!-- Dispatch dweller picker (solo; parties arrive in a later phase) -->
          <PartySelectionModal
            v-model="showDispatchModal"
            :quest="null"
            :vault-id="vaultId"
            :dwellers="dwellerStore.dwellers"
            :current-party="[]"
            :max-party-size="3"
            @assign="handleDispatch"
          />
        </PageContentRail>
      </div>
    </div>
  </div>
</template>

<style scoped>
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
  display: grid;
  grid-template-columns: auto minmax(12rem, 14rem);
  align-items: start;
  gap: 0.75rem;
  width: fit-content;
  max-width: min(80rem, 100%);
}

@media (max-width: 64rem) {
  .map-skeleton {
    grid-template-columns: minmax(0, 1fr);
    max-width: 800px;
  }
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
