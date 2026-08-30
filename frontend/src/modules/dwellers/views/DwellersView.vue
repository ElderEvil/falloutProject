<script setup lang="ts">
import { computed, defineAsyncComponent, inject, onMounted, ref, shallowRef, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useRoomStore } from '@/modules/rooms/stores/room'
import { useIncidentStore } from '@/modules/combat/stores/incident'
import { useSidePanel } from '@/core/composables/useSidePanel'
import { useToast } from '@/core/composables/useToast'
import { happinessService } from '@/modules/dwellers/services/happinessService'
import type { Room } from '@/modules/rooms/models/room'
import SidePanel from '@/core/components/common/SidePanel.vue'
import PageContentRail from '@/core/components/common/PageContentRail.vue'
import PageHeader from '@/core/components/common/PageHeader.vue'
import ComponentLoader from '@/core/components/common/ComponentLoader.vue'
import USkeleton from '@/core/components/ui/USkeleton.vue'
import HappinessDashboard from '@/modules/vault/components/HappinessDashboard.vue'
import {
  useDwellerStore,
  type DwellerSortBy,
  type DwellerStatus,
  type SortDirection,
} from '../stores/dweller'
import DwellerFilterPanel from '../components/DwellerFilterPanel.vue'
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
  death: dwellerDeathStore,
} = useDwellerStore()
const vaultStore = useVaultStore()
const roomStore = useRoomStore()
const incidentStore = useIncidentStore()
const { isCollapsed } = useSidePanel()
const toast = useToast()
const scanlinesEnabled = inject('scanlines', ref(true))
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
  }
})

const fetchDwellers = async (signal?: AbortSignal) => {
  if (authStore.isAuthenticated && vaultId.value) {
    await dwellerStore.fetchDwellersByVault(vaultId.value, authStore.token as string, {
      status: dwellerStore.filterStatus !== 'all' ? dwellerStore.filterStatus : undefined,
      ageGroup: dwellerStore.filterAgeGroup !== 'all' ? dwellerStore.filterAgeGroup : undefined,
      sortBy: dwellerStore.sortBy,
      order: dwellerStore.sortDirection,
      signal,
    })
  }
}

onMounted(async () => {
  // Handle query parameters for sorting/filtering
  const sortByParam = route.query.sortBy as DwellerSortBy | undefined
  const orderParam = route.query.order as SortDirection | undefined
  const filterParam = route.query.filter as DwellerStatus | undefined
  const ageGroupParam = route.query.ageGroup as 'child' | 'teen' | 'adult' | undefined

  if (
    sortByParam &&
    [
      'name',
      'level',
      'happiness',
      'strength',
      'perception',
      'endurance',
      'charisma',
      'intelligence',
      'agility',
      'luck',
    ].includes(sortByParam)
  ) {
    dwellerStore.setSortBy(sortByParam)
  }
  if (orderParam && ['asc', 'desc'].includes(orderParam)) {
    dwellerStore.setSortDirection(orderParam)
  }
  if (
    filterParam &&
    ['idle', 'working', 'exploring', 'questing', 'training', 'resting', 'fighting', 'dead'].includes(filterParam)
  ) {
    dwellerStore.setFilterStatus(filterParam)
  }
  if (ageGroupParam && ['child', 'teen', 'adult'].includes(ageGroupParam)) {
    dwellerStore.setFilterAgeGroup(ageGroupParam)
  }

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
    ])
  }
})

// Watch for filter/sort changes and refetch
watch(
  () => [
    dwellerStore.filterStatus,
    dwellerStore.filterAgeGroup,
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
  router.push(`/vault/${vaultId.value}/radio`)
}

const handleViewLowHappiness = () => {
  dwellerStore.setSortBy('happiness')
  dwellerStore.setSortDirection('asc')
}
</script>

<template>
  <div class="relative min-h-screen bg-terminal-background font-mono text-terminal-green">
    <div v-if="scanlinesEnabled" class="scanlines"></div>

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
            <USkeleton
              v-if="!currentVault && !vaultLoadError"
              width="100%"
              height="120px"
              rounded="lg"
            />
            <p v-else-if="vaultLoadError" role="alert" class="text-danger">{{ vaultLoadError }}</p>
            <HappinessDashboard
              v-else-if="happinessDashboardData"
              :loading="isDashboardLoading"
              :vaultHappiness="happinessDashboardData.vaultHappiness"
              :dwellerCount="happinessDashboardData.dwellerCount"
              :distribution="happinessDashboardData.distribution"
              :idleDwellerCount="happinessDashboardData.idleDwellerCount"
              :activeIncidentCount="happinessDashboardData.activeIncidentCount"
              :lowResourceCount="happinessDashboardData.lowResourceCount"
              :radioHappinessMode="happinessDashboardData.radioHappinessMode"
              @assign-idle="handleAssignIdle"
              @activate-radio="handleActivateRadio"
              @view-low-happiness="handleViewLowHappiness"
            />
          </div>

          <!-- Filter Panel with View Toggle -->
          <div class="w-full mb-4">
            <DwellerFilterPanel
              :show-age-filter="true"
              :show-view-toggle="true"
              :show-bulk-actions="false"
              :vault-id="vaultId"
            />
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

/* Enhanced text styles */

.main-content p,
.main-content span,
.main-content div {
  text-shadow: 0 0 2px var(--color-theme-glow);
}

.scanlines {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: linear-gradient(to bottom, rgba(0, 0, 0, 0.1) 50%, transparent 50%);
  background-size: 100% 2px;
  pointer-events: none;
}
</style>
