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
import { wireToRegistry } from '../utils/atlasProjection'
import { isExploredTile } from '../utils/fog'

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

const explorerTracks = computed<ExplorerTrack[]>(() =>
  buildExplorerTracks(
    // The store can still hold the previous vault's active runs after a vault
    // switch; target_location_id references shared WorldLocation rows, so a
    // stale run could match a location on the new map. Scope to this vault.
    explorationStore.explorations.filter((e) => e.vault_id === vaultId.value),
    mapStore.discoveryRoutes,
    dwellerNames.value
  )
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
    toast.success(`${location.name} — dispatch sent`)
  } catch (err) {
    toast.error(getErrorMessage(err))
  } finally {
    isDispatching.value = false
  }
}

// Scout flow: pick a revealed frontier cell, send a dweller. The duration is
// server-derived (no client ETA), and only one scout submit runs at a time.
const scoutMode = ref(false)
const scoutTarget = ref<{ coord_x: number; coord_y: number } | null>(null)
const lastScout = ref<{ hours: number; coord: { coord_x: number; coord_y: number } } | null>(null)
const isScouting = ref(false)

const lastScoutText = computed(() => {
  const scout = lastScout.value
  if (scout === null) return null
  return `(${scout.coord.coord_x.toFixed(0)}, ${scout.coord.coord_y.toFixed(0)}) · about ${scout.hours} h`
})

const scoutConfirmText = computed(() => {
  const target = scoutTarget.value
  if (target === null) return null
  return `Target (${target.coord_x.toFixed(0)}, ${target.coord_y.toFixed(0)})`
})

async function toggleScoutMode() {
  scoutMode.value = !scoutMode.value
  if (!scoutMode.value) {
    scoutTarget.value = null
    return
  }
  // Like the dispatch picker: the dweller list may be empty when the map opens
  // on its own, so fetch on open and let the panel show loading/empty instead
  // of silently offering nobody to send.
  if (vaultId.value && authStore.token && dwellerStore.dwellers.length === 0) {
    await dwellerStore.fetchDwellersByVault(vaultId.value, authStore.token)
  }
}

// Guard: the target must be a revealed cell (fog), else there is nothing to scout.
// The mask check happens in WorldMap (props-derived); here we only record the pick
// in registry coordinates — the same representation WorldMap's highlight and the
// scout submit both consume, so no second conversion exists to drift.
function handleScoutTarget(coord: { coord_x: number; coord_y: number }) {
  scoutTarget.value = { coord_x: wireToRegistry(coord.coord_x), coord_y: wireToRegistry(coord.coord_y) }
}

function handleScoutInvalid() {
  toast.error('Pick a revealed cell on the edge of the unknown')
}

async function confirmScout(dwellerId: string) {
  const target = scoutTarget.value
  if (isScouting.value || !target || !vaultId.value || !authStore.token) return
  isScouting.value = true
  try {
    const exploration = await explorationStore.scoutFrontier(
      vaultId.value,
      dwellerId,
      target.coord_x,
      target.coord_y
    )
    lastScout.value = { hours: exploration.duration, coord: target }
    scoutMode.value = false
    scoutTarget.value = null
    await mapStore.refreshMap(vaultId.value, authStore.token)
    toast.success(`Scout sent — about ${exploration.duration} h`)
  } catch (err) {
    toast.error(getErrorMessage(err))
  } finally {
    isScouting.value = false
  }
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
            :player-vaults="mapStore.playerVaults"
            :discovery-routes="mapStore.discoveryRoutes"
            :expedition-sites="mapStore.expeditionSites"
            :explorer-tracks="explorerTracks"
            :scout-mode="scoutMode"
            :scout-target="scoutTarget"
            :selected-marker-id="selectedMarkerId"
            @update:selected-marker-id="selectedMarkerId = $event"
            @marker-click="handleMarkerClick"
            @scout-target="handleScoutTarget"
            @scout-invalid="handleScoutInvalid"
          />

          <!-- Scout control + last result -->
          <div class="scout-bar">
            <Button variant="outline" size="sm" @click="toggleScoutMode">
              {{ scoutMode ? 'Cancel scouting' : 'Scout frontier' }}
            </Button>
            <span v-if="scoutMode" class="scout-hint">
              Pick a revealed cell on the edge of the unknown
            </span>
            <span v-else-if="lastScoutText" class="scout-hint">
              Last scout → {{ lastScoutText }}
            </span>
          </div>

          <!-- Scout confirm: pick a dweller, then send -->
          <div v-if="scoutConfirmText" class="scout-confirm">
            <p>{{ scoutConfirmText }} — duration is approximate.</p>
            <p v-if="dwellerStore.isLoading" class="scout-hint">Loading dwellers…</p>
            <p v-else-if="dwellerStore.dwellers.length === 0" class="scout-hint">
              No dwellers available to send.
            </p>
            <div v-else class="scout-dwellers">
              <Button
                v-for="dweller in dwellerStore.dwellers"
                :key="dweller.id"
                variant="outline"
                size="sm"
                :disabled="isScouting"
                @click="confirmScout(dweller.id)"
              >
                Send {{ dweller.first_name }}
              </Button>
            </div>
          </div>

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
.scout-bar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-top: 0.75rem;
}

.scout-hint {
  font-size: 0.75rem;
  opacity: 0.7;
}

.scout-confirm {
  margin-top: 0.5rem;
  padding: 0.5rem 0.75rem;
  border: 1px dashed color-mix(in srgb, var(--color-theme-primary) 40%, transparent);
  font-size: 0.8rem;
}

.scout-dwellers {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.4rem;
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
