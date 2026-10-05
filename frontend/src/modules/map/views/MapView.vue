<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useMapStore } from '../stores/map'
import { useExplorationStore } from '@/modules/exploration/stores/exploration'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { canUseRadaway, isMature, type DwellerShort } from '@/modules/dwellers/models/dweller'
import { useSendToWasteland } from '@/modules/exploration/composables/useSendToWasteland'
import ExplorationDurationModal from '@/modules/exploration/components/ExplorationDurationModal.vue'
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
import { formatHeading } from '../utils/bearing'

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

// Map-first departure: clicking empty/fogged space on the map opens the
// departure flow. The run is free-roam (no target) via the shared send action;
// the pick only chooses the dweller, then the duration/supplies modal opens.
const showDeparturePicker = ref(false)
// Vault that the departure dweller list was fetched for; guards against
// offering another vault's dwellers after a route change.
const departureDwellersVaultId = ref<string | null>(null)
// Compass heading (degrees) chosen by the map click that opened the picker;
// null means a free-roam send. The heading expresses a direction from the
// vault origin, never a promise of arrival at a hidden destination.
const pendingHeading = ref<number | null>(null)
const sendWasteland = useSendToWasteland(() => vaultId.value)
// Admin debug tool: reveal the whole atlas by dropping the fog layer.
const fogDisabled = ref(false)

const vaultMedicalSupplies = computed(() => {
  const vault = vaultId.value ? vaultStore.loadedVaults[vaultId.value] : null
  return { stimpaks: vault?.stimpack ?? 0, radaways: vault?.radaway ?? 0 }
})

const pendingDepartureDweller = computed<DwellerShort | null>(() => {
  const id = sendWasteland.pendingDweller.value?.dwellerId
  if (!id) return null
  return dwellerStore.dwellers.find((d) => d.id === id) ?? null
})

async function handleExploreWasteland(payload?: { headingDegrees: number }) {
  const requestedVaultId = vaultId.value
  if (!requestedVaultId || !authStore.token) return
  pendingHeading.value = payload?.headingDegrees ?? null
  // Like the dispatch picker: the dweller list may be empty when the map opens
  // on its own, so fetch on open and let the panel show loading/empty instead
  // of silently offering nobody to send. Refetch when the list belongs to
  // another vault (route change without reload).
  if (dwellerStore.dwellers.length === 0 || departureDwellersVaultId.value !== requestedVaultId) {
    await dwellerStore.fetchDwellersByVault(requestedVaultId, authStore.token)
    if (vaultId.value !== requestedVaultId) return
    departureDwellersVaultId.value = requestedVaultId
  }
  // Supplies come from the vault record; load it lazily so the duration modal
  // shows real caps instead of zeros.
  await vaultStore.ensureVaultLoaded(requestedVaultId, authStore.token)
  if (vaultId.value !== requestedVaultId) return
  showDeparturePicker.value = true
}

// Dwellers already out (active or returning) cannot be sent again; the picker
// only offers eligible, mature candidates.
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

function pickDepartureDweller(dweller: DwellerShort) {
  const heading = pendingHeading.value
  sendWasteland.open({
    dwellerId: dweller.id,
    firstName: dweller.first_name,
    lastName: dweller.last_name ?? undefined,
    ...(heading !== null ? { headingDegrees: heading } : {}),
  })
  showDeparturePicker.value = false
}

async function handleDepartureConfirm(payload: {
  duration: number
  stimpaks: number
  radaways: number
}) {
  const departureVaultId = vaultId.value
  if (!departureVaultId || !authStore.token) return
  // The shared flow sends the dweller roaming and refreshes the sent vault's
  // supplies on success; the map only refreshes if that vault is still active,
  // so a route change mid-send cannot refetch the wrong one.
  await sendWasteland.confirm(payload, () =>
    Promise.all([
      vaultStore.refreshVault(departureVaultId, authStore.token as string),
      ...(vaultId.value === departureVaultId
        ? [mapStore.refreshMap(departureVaultId, authStore.token as string)]
        : []),
    ]).then(() => undefined)
  )
  // The heading is consumed by the send; the next map click picks a fresh one.
  pendingHeading.value = null
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
    // Vault-scoped departure state must not survive a route change: the picker
    // and any open duration modal belong to the previous vault.
    showDeparturePicker.value = false
    departureDwellersVaultId.value = null
    pendingHeading.value = null
    sendWasteland.cancel()
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
            :fog-disabled="fogDisabled"
            :selected-marker-id="selectedMarkerId"
            @update:selected-marker-id="selectedMarkerId = $event"
            @marker-click="handleMarkerClick"
            @explore-wasteland="handleExploreWasteland"
          />

          <!-- Map-first departure hint: the map itself is the dispatch surface -->
          <div class="map-toolbar">
            <span class="map-hint">Click empty wasteland to send a dweller exploring</span>
          </div>

          <!-- Admin debug: lift the fog to inspect the whole atlas -->
          <div v-if="authStore.isSuperuser" class="map-toolbar">
            <Button variant="outline" size="sm" @click="fogDisabled = !fogDisabled">
              {{ fogDisabled ? 'Restore fog' : 'Remove fog (debug)' }}
            </Button>
          </div>

          <!-- Departure picker: pick a dweller, then the duration/supplies modal -->
          <div v-if="showDeparturePicker" class="departure-picker">
            <p v-if="pendingHeading !== null">
              Explore the wasteland heading
              <span class="heading-badge">{{ formatHeading(pendingHeading) }}</span>
              — pick a dweller to send.
            </p>
            <p v-else>Explore the wasteland — pick a dweller to send roaming.</p>
            <p v-if="dwellerStore.isLoading" class="map-hint">Loading dwellers…</p>
            <p v-else-if="departureCandidates.length === 0" class="map-hint">
              No dwellers available to send.
            </p>
            <div v-else class="departure-dwellers">
              <Button
                v-for="dweller in departureCandidates"
                :key="dweller.id"
                variant="outline"
                size="sm"
                @click="pickDepartureDweller(dweller)"
              >
                Send {{ dweller.first_name
                }}{{ pendingHeading !== null ? ` → ${formatHeading(pendingHeading)}` : '' }}
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

          <!-- Duration/supplies picker for the map departure flow -->
          <ExplorationDurationModal
            :show="sendWasteland.showModal.value"
            :dweller-name="sendWasteland.pendingDweller.value?.firstName ?? ''"
            :heading="
              sendWasteland.headingDegrees.value !== null
                ? formatHeading(sendWasteland.headingDegrees.value)
                : null
            "
            :max-stimpaks="vaultMedicalSupplies.stimpaks"
            :max-radaways="vaultMedicalSupplies.radaways"
            :allow-radaway="canUseRadaway(pendingDepartureDweller)"
            @confirm="handleDepartureConfirm"
            @cancel="sendWasteland.cancel"
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

.map-hint {
  font-size: 0.75rem;
  opacity: 0.7;
}

.departure-picker {
  margin-top: 0.5rem;
  padding: 0.5rem 0.75rem;
  border: 1px dashed color-mix(in srgb, var(--color-theme-primary) 40%, transparent);
  font-size: 0.8rem;
}

.departure-dwellers {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.4rem;
}

.heading-badge {
  display: inline-block;
  padding: 0 0.35rem;
  border: 1px solid color-mix(in srgb, var(--color-theme-primary) 60%, transparent);
  border-radius: 2px;
  color: var(--color-theme-primary);
  font-weight: 700;
  letter-spacing: 0.05em;
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
