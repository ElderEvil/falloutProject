<script setup lang="ts">
import { useDwellerStore } from '@/stores/dweller'
import { useAuthStore } from '@/stores/auth'
import { useVaultStore } from '@/stores/vault'
import { useRoomStore } from '@/stores/room'
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Icon } from '@iconify/vue'
import DwellerStatusBadge from '@/components/dwellers/DwellerStatusBadge.vue'
import DwellerFilterPanel from '@/components/dwellers/DwellerFilterPanel.vue'
import DwellerGridItem from '@/components/dwellers/DwellerGridItem.vue'
import DwellerCardSkeleton from '@/components/dwellers/DwellerCardSkeleton.vue'
import DwellerGridItemSkeleton from '@/components/dwellers/DwellerGridItemSkeleton.vue'
import SidePanel from '@/components/common/SidePanel.vue'
import UTooltip from '@/components/ui/UTooltip.vue'
import UButton from '@/components/ui/UButton.vue'
import { useSidePanel } from '@/composables/useSidePanel'

const authStore = useAuthStore()
const dwellerStore = useDwellerStore()
const vaultStore = useVaultStore()
const roomStore = useRoomStore()
const { isCollapsed } = useSidePanel()
const router = useRouter()
const route = useRoute()
const generatingAI = ref<Record<string, boolean>>({})

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

  const abilityMap: Record<string, { value: number; label: string; icon: string }> = {
    'strength': { value: dweller.strength, label: 'STR', icon: '💪' },
    'perception': { value: dweller.perception, label: 'PER', icon: '👁️' },
    'endurance': { value: dweller.endurance, label: 'END', icon: '❤️' },
    'charisma': { value: dweller.charisma, label: 'CHA', icon: '💬' },
    'intelligence': { value: dweller.intelligence, label: 'INT', icon: '🧠' },
    'agility': { value: dweller.agility, label: 'AGI', icon: '⚡' },
    'luck': { value: dweller.luck, label: 'LCK', icon: '🍀' }
  }

  return abilityMap[room.ability.toLowerCase()] || null
}

// Get color class based on stat value
const getStatColorClass = (value: number) => {
  if (value >= 7) return 'text-green-400'
  if (value >= 4) return 'text-yellow-400'
  return 'text-red-400'
}
</script>

<template>
  <div class="relative min-h-screen bg-terminalBackground font-mono text-terminalGreen">
    <div class="scanlines"></div>

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
          class="flex items-start rounded-lg bg-gray-800 p-4 shadow-md hover:bg-gray-750 transition-all cursor-pointer"
          @click="viewDwellerDetails(dweller.id)"
        >
            <div class="dweller-image-container mr-4">
              <template v-if="dweller.thumbnail_url">
                <img
                  :src="getImageUrl(dweller.thumbnail_url)"
                  alt="Dweller Thumbnail"
                  class="dweller-image rounded-lg"
                />
              </template>
              <template v-else>
                <div class="relative inline-block">
                  <Icon icon="mdi:account-circle" class="h-24 w-24 text-gray-400" />

                  <!-- Generate AI button - always visible when no thumbnail -->
                  <UTooltip
                    text="Generate AI portrait & biography"
                    position="top"
                  >
                    <div
                      @click.stop="generateDwellerInfo(dweller.id)"
                      class="ai-generate-button absolute bottom-1 right-1 rounded-full bg-gray-800 p-1 cursor-pointer hover:bg-gray-700 transition-all"
                      :class="{ 'pointer-events-none': generatingAI[dweller.id] }"
                    >
                      <Icon
                        icon="mdi:sparkles"
                        class="h-5 w-5"
                        :class="{ 'opacity-30': generatingAI[dweller.id] }"
                        :style="{ color: 'var(--color-theme-primary)' }"
                      />

                      <!-- Loading spinner overlay when generating -->
                      <div
                        v-if="generatingAI[dweller.id]"
                        class="absolute inset-0 flex items-center justify-center"
                      >
                        <Icon
                          icon="mdi:loading"
                          class="h-5 w-5 animate-spin"
                          :style="{ color: 'var(--color-theme-primary)' }"
                        />
                      </div>
                    </div>
                  </UTooltip>
                </div>
              </template>
            </div>
            <div class="flex-grow">
              <div class="flex items-center gap-2 mb-2 flex-wrap">
                <h3 class="text-xl font-bold">{{ dweller.first_name }} {{ dweller.last_name }}</h3>
                <DwellerStatusBadge :status="dweller.status" :show-label="true" size="medium" />

                <!-- Room Assignment Badge -->
                <template v-if="getRoomForDweller(dweller.room_id)">
                  <UTooltip :text="`Assigned to ${getRoomForDweller(dweller.room_id)?.name}`" position="top">
                    <div
                      class="room-badge px-2 py-1 rounded text-xs font-semibold bg-gray-800 text-gray-300 border border-gray-600 cursor-pointer hover:bg-gray-700 transition-all flex items-center gap-1"
                      @click.stop="router.push(`/vault/${vaultId}?roomId=${dweller.room_id}`)"
                    >
                      <Icon icon="mdi:office-building" class="h-3 w-3" />
                      <span>{{ getRoomForDweller(dweller.room_id)?.name || 'Room' }}</span>
                    </div>
                  </UTooltip>
                </template>
                <template v-else>
                  <div class="room-badge px-2 py-1 rounded text-xs font-semibold bg-gray-700 text-gray-400 border border-gray-600 flex items-center gap-1">
                    <Icon icon="mdi:account-off" class="h-3 w-3" />
                    <span>Unassigned</span>
                  </div>
                </template>
              </div>
              <p>Level: {{ dweller.level }}</p>
              <p>Health: {{ dweller.health }} / {{ dweller.max_health }}</p>
              <p>Happiness: {{ dweller.happiness }}%</p>
              <!-- Job-relevant SPECIAL stat -->
              <p v-if="getRoomForDweller(dweller.room_id) && getRelevantStatForRoom(dweller, getRoomForDweller(dweller.room_id))" class="mt-1">
                <span class="text-gray-400">Job Stat:</span>
                <span class="ml-2">
                  {{ getRelevantStatForRoom(dweller, getRoomForDweller(dweller.room_id))!.icon }}
                  {{ getRelevantStatForRoom(dweller, getRoomForDweller(dweller.room_id))!.label }}:
                  <span :class="getStatColorClass(getRelevantStatForRoom(dweller, getRoomForDweller(dweller.room_id))!.value)" class="font-bold">
                    {{ getRelevantStatForRoom(dweller, getRoomForDweller(dweller.room_id))!.value }}
                  </span>
                </span>
              </p>
            </div>
            <Icon icon="mdi:chevron-right" class="h-6 w-6 text-terminalGreen" />
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
  text-shadow: 0 0 2px rgba(0, 255, 0, 0.3);
}

.room-badge:hover {
  box-shadow: 0 0 8px rgba(0, 255, 0, 0.4);
}
</style>
