<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, ref, shallowRef, watch } from 'vue'
import {
  useRouter,
  useRoute,
  type LocationQuery,
  type LocationQueryRaw,
  type LocationQueryValueRaw,
} from 'vue-router'
import { Icon } from '@iconify/vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useRoomStore } from '@/modules/rooms/stores/room'
import { useIncidentStore } from '@/modules/combat/stores/incident'
import { useExplorationStore } from '@/modules/exploration/stores/exploration'
import { useSidePanel } from '@/core/composables/useSidePanel'
import { useToast } from '@/core/composables/useToast'
import { happinessService } from '@/modules/dwellers/services/happinessService'
import type { Room } from '@/modules/rooms/models/room'
import SidePanel from '@/core/components/common/SidePanel.vue'
import PageContentRail from '@/core/components/common/PageContentRail.vue'
import PageHeader from '@/core/components/common/PageHeader.vue'
import ComponentLoader from '@/core/components/common/ComponentLoader.vue'
import { Skeleton } from '@/core/components/ui/skeleton'
import HappinessDashboard from '@/modules/vault/components/HappinessDashboard.vue'
import {
  useDwellerStore,
  isDwellerAgeGroup,
  isDwellerSortBy,
  isDwellerStatus,
  isSortDirection,
} from '../stores/dweller'
import { useFeatureFlagsStore } from '../stores/featureFlags'
import DwellerFilterPanel from '../components/DwellerFilterPanel.vue'
import DwellerDisplayControls from '../components/DwellerDisplayControls.vue'
import DwellerBulkActions from '../components/DwellerBulkActions.vue'
import DwellersList from '../components/DwellersList.vue'
import DeadDwellersPanel from '../components/DeadDwellersPanel.vue'

// Lazy load room modal
const RoomDetailModal = defineAsyncComponent({
  loader: () => import('@/modules/rooms/components/RoomDetailModal.vue'),
  loadingComponent: ComponentLoader,
  delay: 200,
  timeout: 10000,
})

const authStore = useAuthStore()
const {
  filter: dwellerStore,
  generation: dwellerGenerationStore,
  management: dwellerManagementStore,
  medical: dwellerMedicalStore,
  death: dwellerDeathStore,
} = useDwellerStore()
const featureFlags = useFeatureFlagsStore()
const vaultStore = useVaultStore()
const roomStore = useRoomStore()
const incidentStore = useIncidentStore()
const explorationStore = useExplorationStore()
const { isCollapsed } = useSidePanel()
const toast = useToast()
const router = useRouter()
const route = useRoute()
const generatingAI = ref<Record<string, boolean>>({})

// Room detail modal state
const showDetailModal = ref(false)
const selectedRoomForDetail = ref<Room | null>(null)

const vaultId = computed(() => route.params.id as string)
const currentVault = computed(() => (vaultId.value ? vaultStore.loadedVaults[vaultId.value] : null))
const revivingDwellers = ref<Record<string, boolean>>({})
const isDeadFilter = computed(() => dwellerStore.filterStatus === 'dead')

/** The dead panel renders a different list, so the count follows whichever is on screen. */
const shownCount = computed(() =>
  isDeadFilter.value ? dwellerDeathStore.deadDwellers.length : dwellerStore.dwellers.length
)

// Applied here rather than on mount so the filter panel can validate a deep-linked race
// on its own. On first load an absent key keeps the persisted value, so localStorage
// still fills the gaps a bare link leaves; after that the URL is authoritative and an
// absent key means the default again.
function applyFiltersFromQuery(query: LocationQuery, resetMissing: boolean): void {
  const { filter, ageGroup, race, faction, sortBy, order } = query

  if (isDwellerStatus(filter)) dwellerStore.setFilterStatus(filter)
  else if (resetMissing) dwellerStore.setFilterStatus('all')

  if (isDwellerAgeGroup(ageGroup)) dwellerStore.setFilterAgeGroup(ageGroup)
  else if (resetMissing) dwellerStore.setFilterAgeGroup('all')

  if (typeof race === 'string' && race) dwellerStore.setFilterRace(race)
  else if (resetMissing) dwellerStore.setFilterRace('all')

  if (typeof faction === 'string' && faction) dwellerStore.setFilterFaction(faction)
  else if (resetMissing) dwellerStore.setFilterFaction('all')

  if (isDwellerSortBy(sortBy)) dwellerStore.setSortBy(sortBy)
  else if (resetMissing) dwellerStore.setSortBy('name')

  if (isSortDirection(order)) dwellerStore.setSortDirection(order)
  else if (resetMissing) dwellerStore.setSortDirection('asc')
}

applyFiltersFromQuery(route.query, false)

// A query-only navigation reuses this component, so setup never runs again: follow the URL.
watch(
  () => route.query,
  (query) => applyFiltersFromQuery(query, true)
)

const FILTER_QUERY_KEYS = ['filter', 'ageGroup', 'race', 'faction', 'sortBy', 'order'] as const

function queryValue(value: LocationQueryValueRaw | LocationQueryValueRaw[] | undefined): string {
  if (Array.isArray(value))
    return value[0] === null || value[0] === undefined ? '' : String(value[0])
  return value === null || value === undefined ? '' : String(value)
}

/** Serialize the filter/sort state, dropping defaults so a bare view keeps a clean URL. */
function filtersToQuery(): LocationQueryRaw {
  const query: LocationQueryRaw = { ...route.query }
  const set = (key: string, value: string | undefined) => {
    if (value === undefined) delete query[key]
    else query[key] = value
  }

  set('filter', dwellerStore.filterStatus === 'all' ? undefined : dwellerStore.filterStatus)
  set('ageGroup', dwellerStore.filterAgeGroup === 'all' ? undefined : dwellerStore.filterAgeGroup)
  set('race', dwellerStore.filterRace === 'all' ? undefined : dwellerStore.filterRace)
  set(
    'faction',
    !featureFlags.factionMechanics || dwellerStore.filterFaction === 'all'
      ? undefined
      : dwellerStore.filterFaction
  )
  set('sortBy', dwellerStore.sortBy === 'name' ? undefined : dwellerStore.sortBy)
  set('order', dwellerStore.sortDirection === 'asc' ? undefined : dwellerStore.sortDirection)
  return query
}

/** Replace (never push) so the URL tracks state without flooding browser history. */
function syncFiltersToUrl(): void {
  const next = filtersToQuery()
  const unchanged = FILTER_QUERY_KEYS.every(
    (key) => queryValue(next[key]) === queryValue(route.query[key])
  )
  if (unchanged) return
  void router.replace({ query: next })
}

watch(
  () => [
    dwellerStore.filterStatus,
    dwellerStore.filterAgeGroup,
    dwellerStore.filterRace,
    dwellerStore.filterFaction,
    dwellerStore.sortBy,
    dwellerStore.sortDirection,
    featureFlags.factionMechanics,
  ],
  syncFiltersToUrl
)

const isAllDwellersLoading = ref(false)
const isIncidentsLoading = ref(false)
const distributionCache = shallowRef<ReturnType<
  typeof happinessService.calculateDistribution
> | null>(null)
const vaultLoadError = ref<string | null>(null)

const isDashboardLoading = computed(
  () =>
    vaultStore.isLoading ||
    isAllDwellersLoading.value ||
    isIncidentsLoading.value ||
    !currentVault.value
)

/**
 * Distribution with stable identity: the game-tick SSE replaces the vault
 * object every tick, which would otherwise recreate this object (and re-render
 * the dashboard) even when no dweller happiness bucket actually changed.
 */
const distribution = computed(() => {
  const next = happinessService.calculateDistribution(dwellerStore.allDwellers)
  const prev = distributionCache.value
  if (prev && JSON.stringify(prev) === JSON.stringify(next)) return prev
  return next
})

watch(
  distribution,
  (next) => {
    distributionCache.value = next
  },
  { immediate: true }
)

const happinessDashboardData = computed(() => {
  if (!currentVault.value) return null

  const population = dwellerStore.allDwellers
  const activeIncidents = incidentStore.activeIncidents

  // Count idle dwellers
  const idleDwellers = population.filter((d) => d.status === 'idle')

  // Count low resource types
  const lowResourceCount = [
    currentVault.value.power / currentVault.value.power_max < 0.3,
    currentVault.value.food / currentVault.value.food_max < 0.3,
    currentVault.value.water / currentVault.value.water_max < 0.3,
  ].filter(Boolean).length

  return {
    vaultHappiness: currentVault.value.happiness || 0,
    dwellerCount: currentVault.value.dweller_count || 0,
    distribution: distribution.value,
    idleDwellerCount: idleDwellers.length,
    activeIncidentCount: activeIncidents.length,
    lowResourceCount,
    radioHappinessMode: currentVault.value.radio_mode === 'happiness',
    irradiatedDwellerCount: population.filter((d) => d.radiation > 0).length,
  }
})

const fetchDwellers = async (signal?: AbortSignal) => {
  await featureFlags.fetchFlags()
  if (authStore.isAuthenticated && vaultId.value) {
    await dwellerStore.fetchWithCurrentFilters(vaultId.value, authStore.token as string, {
      signal,
    })
  }
}

onMounted(async () => {
  // Dashboard aggregates, incidents, and rooms load concurrently: the
  // dashboard's loading flag then flips once instead of flapping
  // skeleton -> content -> skeleton per sequential fetch.
  if (authStore.isAuthenticated && vaultId.value) {
    vaultLoadError.value = null
    isAllDwellersLoading.value = true
    isIncidentsLoading.value = true
    await Promise.all([
      fetchDwellers(),
      vaultStore.loadVault(vaultId.value, authStore.token as string).catch((error: unknown) => {
        vaultLoadError.value = error instanceof Error ? error.message : 'Failed to load vault'
      }),
      dwellerStore.fetchAllDwellers(vaultId.value, authStore.token as string).finally(() => {
        isAllDwellersLoading.value = false
      }),
      incidentStore.fetchIncidents(vaultId.value, authStore.token as string).finally(() => {
        isIncidentsLoading.value = false
      }),
      roomStore.fetchRooms(vaultId.value, authStore.token as string),
      // Recall gating reads the exploration store; a failed load must not block the roster.
      explorationStore
        .fetchExplorationsByVault(vaultId.value, authStore.token as string)
        .catch(() => undefined),
    ])
  }

  // Reflect the restored state so a copied link reproduces this exact view.
  syncFiltersToUrl()
})

// Watch for filter/sort changes and refetch
watch(
  () => [
    dwellerStore.filterStatus,
    dwellerStore.filterAgeGroup,
    dwellerStore.filterRace,
    dwellerStore.filterFaction,
    dwellerStore.sortBy,
    dwellerStore.sortDirection,
  ],
  async (_, __, onCleanup) => {
    const controller = new AbortController()
    onCleanup(() => controller.abort())

    if (dwellerStore.filterStatus === 'dead') {
      // Fetch dead dwellers when dead filter is active
      // Guard: ensure vaultId and token are present before fetching
      if (vaultId.value && authStore.token) {
        await dwellerDeathStore.fetchDeadDwellers(vaultId.value, authStore.token)
      }
    } else {
      await fetchDwellers(controller.signal)
    }
  }
)

// Handle revive action from dead dweller card
const handleRevive = async (dwellerId: string) => {
  if (revivingDwellers.value[dwellerId] || !vaultId.value || !authStore.token) return

  revivingDwellers.value[dwellerId] = true
  try {
    await dwellerDeathStore.reviveDweller(dwellerId, authStore.token)
    // Refresh dead dwellers list
    await dwellerDeathStore.fetchDeadDwellers(vaultId.value, authStore.token)
  } finally {
    revivingDwellers.value[dwellerId] = false
  }
}

const navigateToGraveyard = () => {
  router.push(`/vault/${vaultId.value}/dwellers/graveyard`)
}

// Clicking a dweller opens the standalone full-page detail route.
const handleViewDetails = (dwellerId: string) => {
  router.push(`/vault/${vaultId.value}/dwellers/${dwellerId}`)
}

const generateDwellerInfo = async (dwellerId: string) => {
  generatingAI.value[dwellerId] = true
  try {
    const result = await dwellerGenerationStore.generateDwellerInfo(
      dwellerId,
      authStore.token as string
    )
    if (result) {
      // Refresh the dweller list to get the updated thumbnail_url
      await fetchDwellers()
      // Force refresh the detailed dweller data
      await dwellerStore.fetchDwellerDetails(dwellerId, authStore.token as string, true)
    }
  } catch {
    toast.error('Failed to generate dweller information')
  } finally {
    generatingAI.value[dwellerId] = false
  }
}

// Open room detail modal
const openRoomModal = (roomId: string) => {
  const room = roomStore.rooms.find((r) => r.id === roomId)
  if (room) {
    selectedRoomForDetail.value = room
    showDetailModal.value = true
  }
}

const closeRoomModal = () => {
  showDetailModal.value = false
  selectedRoomForDetail.value = null
}

const handleQuickUnassign = async (dwellerId: string) => {
  if (!authStore.token) return
  try {
    await dwellerManagementStore.unassignDwellerFromRoom(dwellerId, authStore.token)
  } catch {
    toast.error('Failed to unassign dweller from room')
  }
}

// Happiness dashboard event handlers
const handleAssignIdle = () => {
  dwellerStore.setFilterStatus('idle')
}

const handleActivateRadio = () => {
  router.push(`/vault/${vaultId.value}`)
}

const handleViewLowHappiness = () => {
  dwellerStore.setSortBy('happiness')
  dwellerStore.setSortDirection('asc')
}

const treatingDwellers = ref(false)

const handleTreatIrradiated = async () => {
  if (!vaultId.value || !authStore.token || treatingDwellers.value) return

  treatingDwellers.value = true
  try {
    await dwellerMedicalStore.distributeRecoverySupplies(vaultId.value, authStore.token)
  } finally {
    treatingDwellers.value = false
  }
}
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
            title="Dwellers"
            icon="mdi:account-group"
            subtitle="Assign, train & equip your vault population."
          />

          <!-- Happiness Dashboard -->
          <div class="mb-6">
            <Skeleton
              v-if="!currentVault && !vaultLoadError"
              class="h-[120px] w-full rounded-lg"
            />
            <p v-else-if="vaultLoadError" role="alert" class="text-danger">{{ vaultLoadError }}</p>
            <details v-else-if="happinessDashboardData" class="happiness-overview">
              <summary
                class="flex cursor-pointer flex-wrap items-center justify-between gap-4 rounded-lg border-2 border-theme-primary/20 bg-surface-sunken px-4 py-3 text-theme-primary"
              >
                <span class="text-xs font-bold uppercase tracking-[0.12em] text-theme-primary/70">
                  Happiness Overview
                </span>
                <span class="flex flex-wrap items-center justify-end gap-3 text-sm font-bold">
                  <span>{{ happinessDashboardData.vaultHappiness }}% happiness</span>
                  <span class="text-theme-primary/60"
                    >{{ happinessDashboardData.dwellerCount }} dwellers</span
                  >
                  <span
                    v-if="
                      happinessDashboardData.lowResourceCount ||
                      happinessDashboardData.activeIncidentCount ||
                      happinessDashboardData.irradiatedDwellerCount ||
                      happinessDashboardData.idleDwellerCount >= 3 ||
                      happinessDashboardData.vaultHappiness < 50
                    "
                    class="text-warning"
                  >
                    Attention needed
                  </span>
                  <Icon icon="mdi:chevron-down" class="h-5 w-5" :ariaHidden="true" />
                </span>
              </summary>
              <HappinessDashboard
                :loading="isDashboardLoading"
                :vaultHappiness="happinessDashboardData.vaultHappiness"
                :dwellerCount="happinessDashboardData.dwellerCount"
                :distribution="happinessDashboardData.distribution"
                :idleDwellerCount="happinessDashboardData.idleDwellerCount"
                :activeIncidentCount="happinessDashboardData.activeIncidentCount"
                :lowResourceCount="happinessDashboardData.lowResourceCount"
                :radioHappinessMode="happinessDashboardData.radioHappinessMode"
                :irradiatedDwellerCount="happinessDashboardData.irradiatedDwellerCount"
                :treatingDwellers="treatingDwellers"
                @assign-idle="handleAssignIdle"
                @activate-radio="handleActivateRadio"
                @view-low-happiness="handleViewLowHappiness"
                @treat-irradiated="handleTreatIrradiated"
              />
            </details>
          </div>

          <!-- Filters narrow the roster; Sort and View live on the list toolbar below. -->
          <div class="w-full mb-4">
            <DwellerFilterPanel
              :show-age-filter="!isDeadFilter"
              :show-identity-filters="!isDeadFilter"
              :show-active-filter-summary="true"
            />
          </div>

          <div class="list-toolbar">
            <DwellerDisplayControls :show-view="true" />
            <span class="list-toolbar-count">{{ shownCount }} shown</span>
          </div>

          <!-- Bulk Actions - Separate Section -->
          <div class="w-full mb-6">
            <DwellerBulkActions :vault-id="vaultId" />
          </div>

          <div class="min-w-0">
            <DeadDwellersPanel
              v-if="isDeadFilter"
              :dwellers="dwellerDeathStore.deadDwellers"
              :is-loading="dwellerDeathStore.isDeadLoading"
              :reviving-dwellers="revivingDwellers"
              @revive="handleRevive"
              @view-details="handleViewDetails"
              @view-graveyard="navigateToGraveyard"
            />
            <DwellersList
              v-else
              :dwellers="dwellerStore.dwellers"
              :generating-a-i="generatingAI"
              :is-loading="dwellerStore.isLoading"
              :rooms="roomStore.rooms"
              :view-mode="dwellerStore.viewMode"
              :columns="dwellerStore.tableColumns"
              @view-details="handleViewDetails"
              @generate-ai="generateDwellerInfo"
              @open-room="openRoomModal"
              @quick-unassign="handleQuickUnassign"
              @room-click="(roomId) => router.push(`/vault/${vaultId}?roomId=${roomId}`)"
            />
          </div>
        </PageContentRail>
      </div>
    </div>

    <!-- Room Detail Modal -->
    <RoomDetailModal
      v-if="selectedRoomForDetail"
      :room="selectedRoomForDetail"
      :vault-id="vaultId"
      v-model="showDetailModal"
      @close="closeRoomModal"
    />
  </div>
</template>

<style scoped>
.vault-layout {
  display: flex;
  min-height: 100vh;
}

.main-content {
  flex: 1;
  margin-left: 240px; /* Width of expanded side panel */
  transition: margin-left 0.3s ease;
  font-weight: 600; /* Bold font for better readability */
  letter-spacing: 0.025em; /* Slight letter spacing for clarity */
  line-height: 1.6; /* Better line height for readability */
}

.main-content.collapsed {
  margin-left: 64px;
}

.happiness-overview > summary {
  list-style: none;
}

.happiness-overview > summary::-webkit-details-marker {
  display: none;
}

.happiness-overview > summary:focus-visible {
  outline: 2px solid var(--color-theme-primary);
  outline-offset: 2px;
}

.list-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.list-toolbar-count {
  color: var(--color-theme-primary);
  font-size: 0.8125rem;
  /* Matches the Happiness overview's muted dweller count so the two bars read as a pair. */
  opacity: 0.6;
}

/* Enhanced text styles */

.main-content p,
.main-content span,
.main-content div {
  text-shadow: 0 0 2px var(--color-theme-glow);
}
</style>
