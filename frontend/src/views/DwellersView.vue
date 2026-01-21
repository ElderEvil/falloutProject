<script setup lang="ts">
import { useDwellerStore, type DwellerSortBy, type DwellerStatus, type SortDirection } from '@/stores/dweller'
import { useAuthStore } from '@/stores/auth'
import { useVaultStore } from '@/stores/vault'
import { useRoomStore } from '@/stores/room'
import { computed, defineAsyncComponent, inject, onMounted, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Icon } from '@iconify/vue'
import DwellerStatusBadge from '@/components/dwellers/DwellerStatusBadge.vue'
import DwellerFilterPanel from '@/components/dwellers/DwellerFilterPanel.vue'
import DwellerGridItem from '@/components/dwellers/DwellerGridItem.vue'
import DwellerCardSkeleton from '@/components/dwellers/DwellerCardSkeleton.vue'
import DwellerGridItemSkeleton from '@/components/dwellers/DwellerGridItemSkeleton.vue'
import SidePanel from '@/core/components/common/SidePanel.vue'
import UTooltip from '@/core/components/ui/UTooltip.vue'
import UButton from '@/core/components/ui/UButton.vue'
import ComponentLoader from '@/core/components/common/ComponentLoader.vue'
import { useSidePanel } from '@/core/composables/useSidePanel'
import type { Room } from '@/models/room'

// Lazy load room modal
const RoomDetailModal = defineAsyncComponent({
  loader: () => import('@/components/rooms/RoomDetailModal.vue'),
  loadingComponent: ComponentLoader,
  delay: 200,
  timeout: 10000,
})

const authStore = useAuthStore()
const dwellerStore = useDwellerStore()
const vaultStore = useVaultStore()
const roomStore = useRoomStore()
const { isCollapsed } = useSidePanel()
const scanlinesEnabled = inject('scanlines', ref(true))
const router = useRouter()
const route = useRoute()
const generatingAI = ref<Record<string, boolean>>({})

// Room detail modal state
const showDetailModal = ref(false)
const selectedRoomForDetail = ref<Room | null>(null)

const vaultId = computed(() => route.params.id as string)
const currentVault = computed(() => vaultId.value ? vaultStore.loadedVaults[vaultId.value] : null)

const fetchDwellers = async () => {
  if (authStore.isAuthenticated && vaultId.value) {
    await dwellerStore.fetchDwellersByVault(vaultId.value, authStore.token as string, {
      status: dwellerStore.filterStatus !== 'all' ? dwellerStore.filterStatus : undefined,
      sortBy: dwellerStore.sortBy,
      order: dwellerStore.sortDirection
    })
  }
}

onMounted(async () => {
  // Handle query parameters for sorting/filtering
  const sortByParam = route.query.sortBy as DwellerSortBy | undefined
  const orderParam = route.query.order as SortDirection | undefined
  const filterParam = route.query.filter as DwellerStatus | undefined

  if (sortByParam && ['name', 'level', 'happiness', 'strength', 'perception', 'endurance', 'charisma', 'intelligence', 'agility', 'luck'].includes(sortByParam)) {
    dwellerStore.setSortBy(sortByParam)
  }
  if (orderParam && ['asc', 'desc'].includes(orderParam)) {
    dwellerStore.setSortDirection(orderParam)
  }
  if (filterParam && ['idle', 'working', 'exploring', 'training', 'resting', 'dead'].includes(filterParam)) {
    dwellerStore.setFilterStatus(filterParam)
  }

  await fetchDwellers()
  // Fetch rooms to show room assignments
  if (authStore.isAuthenticated && vaultId.value) {
    await roomStore.fetchRooms(vaultId.value, authStore.token as string)
  }
})

// Watch for filter/sort changes and refetch
watch(
  () => [dwellerStore.filterStatus, dwellerStore.sortBy, dwellerStore.sortDirection],
  async () => {
    await fetchDwellers()
  }
)

const viewDwellerDetails = (dwellerId: string) => {
  router.push(`/vault/${vaultId.value}/dwellers/${dwellerId}`)
}

const getImageUrl = (imagePath: string) => {
  return imagePath.startsWith('http') ? imagePath : `http://${imagePath}`
}

const navigateToChatPage = (dwellerId: string) => {
  router.push(`/dweller/${dwellerId}/chat`)
}

const generateDwellerInfo = async (dwellerId: string) => {
  generatingAI.value[dwellerId] = true
  try {
    const result = await dwellerStore.generateDwellerInfo(dwellerId, authStore.token as string)
    if (result) {
      // Refresh the dweller list to get the updated thumbnail_url
      await fetchDwellers()
      // Force refresh the detailed dweller data
      await dwellerStore.fetchDwellerDetails(dwellerId, authStore.token as string, true)
    }
  } catch (error) {
    console.error('Error generating info with AI:', error)
  } finally {
    generatingAI.value[dwellerId] = false
  }
}

// Get room info for a dweller
const getRoomForDweller = computed(() => (roomId: string | null | undefined) => {
  if (!roomId) return null
  return roomStore.rooms.find(room => room.id === roomId)
})

// Get relevant SPECIAL stat for room's required ability
const getRelevantStatForRoom = (dweller: any, room: any) => {
  if (!room?.ability) return null

  const abilityMap: Record<string, { value: number; label: string; icon: string; color: string }> = {
    'strength': { value: dweller.strength, label: 'STR', icon: 'mdi:arm-flex', color: 'text-red-400' },
    'perception': { value: dweller.perception, label: 'PER', icon: 'mdi:eye', color: 'text-blue-400' },
    'endurance': { value: dweller.endurance, label: 'END', icon: 'mdi:shield', color: 'text-orange-400' },
    'charisma': { value: dweller.charisma, label: 'CHA', icon: 'mdi:account-voice', color: 'text-pink-400' },
    'intelligence': { value: dweller.intelligence, label: 'INT', icon: 'mdi:brain', color: 'text-purple-400' },
    'agility': { value: dweller.agility, label: 'AGI', icon: 'mdi:run-fast', color: 'text-cyan-400' },
    'luck': { value: dweller.luck, label: 'LCK', icon: 'mdi:clover', color: 'text-green-400' }
  }

  return abilityMap[room.ability.toLowerCase()] || null
}

// Get color class based on stat value
const getStatColorClass = (value: number) => {
  if (value >= 7) return 'text-green-400'
  if (value >= 4) return 'text-yellow-400'
  return 'text-red-400'
}

// Open room detail modal
const openRoomModal = (roomId: string) => {
  const room = roomStore.rooms.find(r => r.id === roomId)
  if (room) {
    selectedRoomForDetail.value = room
    showDetailModal.value = true
  }
}

const closeRoomModal = () => {
  showDetailModal.value = false
  selectedRoomForDetail.value = null
}
</script>

<template>
  <div class="relative min-h-screen bg-terminalBackground font-mono text-terminalGreen">
    <div v-if="scanlinesEnabled" class="scanlines"></div>

    <div class="vault-layout">
      <!-- Side Panel -->
      <SidePanel />

      <!-- Main Content Area -->
      <div class="main-content flicker" :class="{ collapsed: isCollapsed }">
        <div class="container mx-auto flex flex-col items-center justify-center px-4 py-8 lg:px-8">
      <h1 class="mb-8 text-4xl font-bold">
        {{ currentVault ? `Vault ${currentVault.number} Dwellers` : 'Dwellers' }}
      </h1>

      <!-- Filter Panel with View Toggle -->
      <div class="w-full mb-6">
        <DwellerFilterPanel :show-view-toggle="true" />
      </div>

      <!-- List View -->
      <ul v-if="dwellerStore.viewMode === 'list'" class="w-full space-y-4">
        <!-- Loading Skeletons -->
        <template v-if="dwellerStore.isLoading">
          <DwellerCardSkeleton v-for="i in 3" :key="`skeleton-${i}`" />
        </template>

        <!-- Dweller Cards -->
        <li
          v-else
          v-for="dweller in dwellerStore.dwellers"
          :key="dweller.id"
          class="flex items-center gap-3 rounded border border-gray-700 bg-gray-800/50 p-3 hover:bg-gray-800 transition-all cursor-pointer"
          @click="viewDwellerDetails(dweller.id)"
        >
            <!-- Avatar - smaller, no generate button -->
            <div class="flex-shrink-0">
              <template v-if="dweller.thumbnail_url">
                <img
                  :src="getImageUrl(dweller.thumbnail_url)"
                  alt="Dweller Thumbnail"
                  class="h-16 w-16 rounded object-cover"
                />
              </template>
              <template v-else>
                <Icon icon="mdi:account-circle" class="h-16 w-16" :style="{ color: 'var(--color-theme-primary)', opacity: 0.6 }" />
              </template>
            </div>

            <!-- Name & Level -->
            <div class="flex flex-col" style="min-width: 140px;">
              <h3 class="font-bold text-base text-terminalGreen">{{ dweller.first_name }} {{ dweller.last_name }}</h3>
              <p class="text-sm text-gray-400">Level {{ dweller.level }}</p>
            </div>

            <!-- Separator -->
            <div class="h-10 w-px bg-gray-600/50 flex-shrink-0"></div>

            <!-- Status Badge -->
            <div class="flex-shrink-0">
              <DwellerStatusBadge :status="dweller.status" :show-label="true" size="small" />
            </div>

            <!-- Separator -->
            <div class="h-10 w-px bg-gray-600/50 flex-shrink-0"></div>

            <!-- Health & Happiness -->
            <div class="flex items-center gap-4">
              <div class="flex items-center gap-1.5">
                <Icon icon="mdi:heart" class="h-4 w-4 text-red-400" />
                <span class="text-sm font-semibold">{{ dweller.health }} / {{ dweller.max_health }}</span>
              </div>
              <div class="flex items-center gap-1">
                <Icon icon="mdi:emoticon-happy" class="h-4 w-4 text-yellow-400" />
                <span class="text-sm font-semibold">{{ dweller.happiness }}%</span>
              </div>
            </div>

            <!-- Separator (only if job stat exists) -->
            <div v-if="getRoomForDweller(dweller.room_id) && getRelevantStatForRoom(dweller, getRoomForDweller(dweller.room_id))" class="h-10 w-px bg-gray-600/50 flex-shrink-0"></div>

            <!-- Job Stat -->
            <div v-if="getRoomForDweller(dweller.room_id) && getRelevantStatForRoom(dweller, getRoomForDweller(dweller.room_id))" class="flex items-center gap-1.5">
              <span class="text-sm text-gray-400">Job Stat:</span>
              <div class="flex items-center gap-1.5">
                <Icon
                  :icon="getRelevantStatForRoom(dweller, getRoomForDweller(dweller.room_id))!.icon"
                  :class="getRelevantStatForRoom(dweller, getRoomForDweller(dweller.room_id))!.color"
                  class="h-4 w-4"
                />
                <span class="text-sm">{{ getRelevantStatForRoom(dweller, getRoomForDweller(dweller.room_id))!.label }}</span>
                <span :class="getStatColorClass(getRelevantStatForRoom(dweller, getRoomForDweller(dweller.room_id))!.value)" class="text-sm font-bold">
                  {{ getRelevantStatForRoom(dweller, getRoomForDweller(dweller.room_id))!.value }}
                </span>
              </div>
            </div>

            <!-- Room Assignment - right side -->
            <div class="ml-auto flex items-center gap-2">
              <template v-if="getRoomForDweller(dweller.room_id)">
                <div
                  class="px-3 py-1.5 rounded text-sm font-medium bg-gray-700/80 text-gray-200 border border-gray-600 cursor-pointer hover:bg-gray-700 transition-all"
                  @click.stop="openRoomModal(dweller.room_id!)"
                >
                  {{ getRoomForDweller(dweller.room_id)?.name }}
                </div>
              </template>

              <!-- Chevron -->
              <Icon icon="mdi:chevron-right" class="h-5 w-5 text-terminalGreen/50 flex-shrink-0" />
            </div>
        </li>
      </ul>

      <!-- Grid View -->
      <div v-else class="w-full dweller-grid">
        <!-- Loading Skeletons -->
        <template v-if="dwellerStore.isLoading">
          <DwellerGridItemSkeleton v-for="i in 6" :key="`grid-skeleton-${i}`" />
        </template>

        <!-- Grid Items -->
        <DwellerGridItem
          v-else
          v-for="dweller in dwellerStore.dwellers"
          :key="dweller.id"
          :dweller="dweller"
          :room-name="getRoomForDweller(dweller.room_id)?.name"
          :room-ability="getRoomForDweller(dweller.room_id)?.ability"
          :generating-a-i="generatingAI[dweller.id]"
          @click="viewDwellerDetails(dweller.id)"
          @generate-ai="generateDwellerInfo(dweller.id)"
          @room-click="router.push(`/vault/${vaultId}?roomId=${dweller.room_id}`)"
        />
      </div>
        </div>
      </div>
    </div>

    <!-- Room Detail Modal -->
    <RoomDetailModal
      v-if="selectedRoomForDetail"
      :room="selectedRoomForDetail"
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
.main-content h1,
.main-content h2,
.main-content h3 {
  font-weight: 700;
  text-shadow: 0 0 8px var(--color-theme-glow);
}

.main-content p,
.main-content span,
.main-content div {
  text-shadow: 0 0 2px var(--color-theme-glow);
}

.dweller-image {
  width: 6rem;
  height: auto;
  object-fit: cover;
}

/* AI Generate Button Animation (Small - Collapsed View) */
.ai-generate-button {
  animation: pulse-glow 2s ease-in-out infinite;
  z-index: 10;
}

.ai-generate-button:hover {
  animation: none;
  box-shadow: 0 0 20px var(--color-theme-primary);
}

/* AI Generate Button (Large - Expanded View) */
.ai-generate-button-large {
  animation: pulse-glow-large 2s ease-in-out infinite;
  z-index: 10;
}

.ai-generate-button-large:hover {
  animation: none;
  box-shadow: 0 0 30px var(--color-theme-primary);
}

@keyframes pulse-glow {
  0%, 100% {
    box-shadow: 0 0 5px var(--color-theme-glow);
  }
  50% {
    box-shadow: 0 0 15px var(--color-theme-primary);
  }
}

@keyframes pulse-glow-large {
  0%, 100% {
    box-shadow: 0 0 10px var(--color-theme-glow);
  }
  50% {
    box-shadow: 0 0 25px var(--color-theme-primary);
  }
}

/* Dweller Grid */
.dweller-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1.5rem;
  width: 100%;
}

@media (max-width: 640px) {
  .dweller-grid {
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 1rem;
  }
}

@media (min-width: 1536px) {
  .dweller-grid {
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  }
}

.text-terminalGreen {
  color: var(--color-theme-primary);
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

/* Room Badge Styling */
.room-badge {
  font-family: monospace;
  text-shadow: 0 0 2px var(--color-theme-glow);
}

.room-badge:hover {
  box-shadow: 0 0 8px var(--color-theme-glow);
}
</style>
