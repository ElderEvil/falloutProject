<script setup lang="ts">
import { computed, defineAsyncComponent, inject, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useRoomStore } from '@/modules/rooms/stores/room'
import { useVaultStore } from '../stores/vault'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useExplorationStore } from '@/modules/exploration/stores/exploration'
import { useIncidentStore } from '@/modules/combat/stores/incident'
import RoomGrid from '@/modules/rooms/components/RoomGrid.vue'
import BuildModeButton from '@/core/components/common/BuildModeButton.vue'
import RoomMenu from '@/modules/rooms/components/RoomMenu.vue'
import ResourceBar from '@/core/components/common/ResourceBar.vue'
import GameControlPanel from '@/core/components/common/GameControlPanel.vue'
import UnassignedDwellers from '@/modules/dwellers/components/UnassignedDwellers.vue'
import WastelandPanel from '@/modules/exploration/components/WastelandPanel.vue'
import IncidentAlert from '@/modules/combat/components/incidents/IncidentAlert.vue'
import ComponentLoader from '@/core/components/common/ComponentLoader.vue'
import UTooltip from '@/core/components/ui/UTooltip.vue'
import SidePanel from '@/core/components/common/SidePanel.vue'
import { useSidePanel } from '@/core/composables/useSidePanel'
import type { Room } from '@/modules/rooms/models/room'
import { Icon } from '@iconify/vue'

// Lazy load heavy modal
const CombatModal = defineAsyncComponent({
  loader: () => import('@/modules/combat/components/incidents/CombatModal.vue'),
  loadingComponent: ComponentLoader,
  delay: 200,
  timeout: 10000,
})

interface Position {
  x: number
  y: number
}

const route = useRoute()
const authStore = useAuthStore()
const roomStore = useRoomStore()
const vaultStore = useVaultStore()
const dwellerStore = useDwellerStore()
const explorationStore = useExplorationStore()
const incidentStore = useIncidentStore()
const { isCollapsed } = useSidePanel()
const scanlinesEnabled = inject('scanlines', ref(true))
const showRoomMenu = ref(false)
const selectedRoom = ref<Room | null>(null)
const isPlacingRoom = ref(false)
const isLoading = ref(true)
const errorMessage = ref<string | null>(null)
const showCombatModal = ref(false)
const selectedIncidentId = ref<string | null>(null)
const highlightedRoomId = ref<string | null>(null)

const buildModeActive = computed(() => showRoomMenu.value || isPlacingRoom.value)

// Get vault ID from route params
const vaultId = computed(() => route.params.id as string)

// Use loadedVaults for real-time updates
const currentVault = computed(() => {
  return vaultId.value ? vaultStore.loadedVaults[vaultId.value] : null
})

const bottleCaps = computed(() => currentVault.value?.bottle_caps ?? 0)
const dwellersCount = computed(() => currentVault.value?.dweller_count ?? 0)
const happiness = computed(() => currentVault.value?.happiness ?? 0)

const happinessColor = computed(() => {
  const h = happiness.value;
  if (h >= 75) return 'text-terminalGreen';
  if (h >= 50) return 'text-green-400';
  if (h >= 25) return 'text-yellow-400';
  return 'text-red-500';
});

const energy = computed(() => ({
  current: currentVault.value?.power ?? 0,
  max: currentVault.value?.power_max ?? 100
}))
const food = computed(() => ({
  current: currentVault.value?.food ?? 0,
  max: currentVault.value?.food_max ?? 100
}))
const water = computed(() => ({
  current: currentVault.value?.water ?? 0,
  max: currentVault.value?.water_max ?? 100
}))

const activeIncidents = computed(() => incidentStore.activeIncidents)

const loadVaultData = async (id: string) => {
  if (!id) {
    errorMessage.value = 'No vault ID provided in URL'
    isLoading.value = false
    return
  }

  if (!authStore.token) {
    errorMessage.value = 'Not authenticated. Please log in again.'
    isLoading.value = false
    return
  }

  try {
    isLoading.value = true
    errorMessage.value = null

    // Fetch vault list
    await vaultStore.fetchVaults(authStore.token)

    // Load the specific vault data
    await vaultStore.refreshVault(id, authStore.token)

    // Verify vault was loaded
    if (!vaultStore.loadedVaults[id]) {
      throw new Error('Vault not found')
    }

    // Fetch rooms for this vault
    await roomStore.fetchRooms(id, authStore.token)

    // Fetch dwellers for this vault
    await dwellerStore.fetchDwellersByVault(id, authStore.token)

    // Fetch explorations for this vault
    try {
      await explorationStore.fetchExplorationsByVault(id, authStore.token)
    } catch (error) {
      console.error('[VaultView] Failed to load explorations:', error)
      // Don't fail the whole page load if explorations fail
    }

    // Fetch game state and start polling
    try {
      await vaultStore.fetchGameState(id, authStore.token)
      if (!vaultStore.gameState?.is_paused) {
        vaultStore.startResourcePolling()
      }
    } catch (error) {
      // Game state not available, continuing without it
    }

    // Start incident polling
    incidentStore.startPolling(id, authStore.token)

    isLoading.value = false
  } catch (error) {
    console.error('Failed to load vault:', error)
    errorMessage.value = error instanceof Error ? error.message : 'Failed to load vault data'
    isLoading.value = false
  }
}

// Watch for room highlight query parameter
watch(() => route.query.roomId, (newRoomId) => {
  if (newRoomId && typeof newRoomId === 'string') {
    highlightedRoomId.value = newRoomId
    // Clear highlight after 3 seconds
    setTimeout(() => {
      highlightedRoomId.value = null
    }, 3000)
  }
}, { immediate: true })

// Watch for vault ID changes in the URL
watch(() => vaultId.value, (newId) => {
  if (newId) {
    vaultStore.stopResourcePolling()
    incidentStore.stopPolling()
    loadVaultData(newId)
  }
}, { immediate: true })

onMounted(async () => {
  // Initial load is handled by the watcher
})

onUnmounted(() => {
  // Clean up polling when component is unmounted
  vaultStore.stopResourcePolling()
  incidentStore.stopPolling()
})

const toggleBuildMode = async () => {
  if (buildModeActive.value) {
    // Cancel building
    showRoomMenu.value = false
    isPlacingRoom.value = false
    selectedRoom.value = null
  } else {
    // Enter build mode
    if (roomStore.availableRooms.length === 0) {
      await roomStore.fetchRoomsData(authStore.token as string)
    }
    showRoomMenu.value = true
  }
}

const handleRoomSelected = (room: Room) => {
  selectedRoom.value = room
  showRoomMenu.value = false
  isPlacingRoom.value = true
}

const handleRoomPlaced = async (position: Position) => {
  if (selectedRoom.value && isPlacingRoom.value) {
    isPlacingRoom.value = false
    selectedRoom.value = null
  }
}

const handleIncidentClicked = (incidentId: string) => {
  selectedIncidentId.value = incidentId
  showCombatModal.value = true
}

const handleCombatModalClose = () => {
  showCombatModal.value = false
  selectedIncidentId.value = null
}

const handleIncidentResolved = async () => {
  // Refresh vault data to update resources/stats
  if (vaultId.value && authStore.token) {
    await vaultStore.refreshVault(vaultId.value, authStore.token)
  }
}
</script>

<template>
  <div class="relative min-h-screen bg-terminalBackground font-mono text-terminalGreen">
    <div v-if="scanlinesEnabled" class="scanlines"></div>

    <!-- Loading State -->
    <div v-if="isLoading" class="flex min-h-screen items-center justify-center">
      <div class="text-center">
        <div class="mb-4 text-6xl animate-pulse">⚙️</div>
        <p class="text-xl text-terminalGreen">Loading Vault Data...</p>
      </div>
    </div>

    <!-- Error State -->
    <div v-else-if="errorMessage" class="flex min-h-screen items-center justify-center">
      <div class="max-w-md rounded border-2 border-red-500 bg-gray-900 p-8 text-center">
        <div class="mb-4 text-6xl">⚠️</div>
        <h2 class="mb-4 text-2xl font-bold text-red-500">Error Loading Vault</h2>
        <p class="mb-6 text-terminalGreen">{{ errorMessage }}</p>
        <router-link
          to="/"
          class="rounded bg-terminalGreen px-6 py-2 font-bold text-black hover:bg-green-400"
        >
          Go to Vault List
        </router-link>
      </div>
    </div>

    <!-- Main Vault View -->
    <div v-else class="vault-layout">
      <!-- Side Panel -->
      <SidePanel />

      <!-- Main Content Area -->
      <div class="main-content flicker" :class="{ collapsed: isCollapsed }">
        <div class="container mx-auto flex flex-col items-center justify-center px-4 py-8 lg:px-8">
      <div class="mb-8 flex w-full items-center justify-between space-x-8">
        <!-- Dwellers Count and Happiness -->
        <div class="flex items-center space-x-4">
          <UTooltip text="Total dwellers in vault" position="bottom">
            <div class="flex items-center space-x-2 cursor-help" tabindex="0">
              <Icon icon="mdi:account-group" class="h-8 w-8 text-terminalGreen" />
              <p>{{ dwellersCount }}</p>
            </div>
          </UTooltip>
          <UTooltip :text="`Vault Happiness: ${happiness}%\n${happiness >= 75 ? '😊 Excellent morale!' : happiness >= 50 ? '😐 Acceptable morale' : happiness >= 25 ? '😟 Low morale - needs attention' : '😢 Critical - dwellers are unhappy!'}`" position="bottom">
            <div class="flex items-center space-x-2 cursor-help" tabindex="0">
              <Icon icon="mdi:emoticon-happy" class="h-6 w-6" :class="happinessColor" />
              <p :class="happinessColor">{{ happiness }}%</p>
            </div>
          </UTooltip>
        </div>

        <!-- Resources in the Middle -->
        <div class="flex justify-center space-x-8">
          <ResourceBar :current="energy.current" :max="energy.max" icon="mdi:lightning-bolt" label="Power" />
          <ResourceBar :current="food.current" :max="food.max" icon="mdi:food-apple" label="Food" />
          <ResourceBar :current="water.current" :max="water.max" icon="mdi:water" label="Water" />
        </div>

        <!-- Bottle Caps and Game Controls -->
        <div class="flex items-center space-x-4">
          <UTooltip :text="`Bottle Caps: ${bottleCaps}\nVault currency for construction and upgrades`" position="bottom">
            <div class="flex items-center space-x-2 cursor-help" tabindex="0">
              <Icon icon="mdi:currency-usd" class="h-6 w-6 text-terminalGreen" />
              <p>{{ bottleCaps }}</p>
            </div>
          </UTooltip>
          <GameControlPanel v-if="vaultId" :vaultId="vaultId" />
        </div>
      </div>

      <!-- Incident Alert Banner -->
      <div v-if="activeIncidents.length > 0" class="w-full mb-4">
        <IncidentAlert :incidents="activeIncidents" @click="handleIncidentClicked" />
      </div>

      <!-- Unassigned Dwellers Panel -->
      <div class="w-full mb-4">
        <UnassignedDwellers />
      </div>

      <!-- Wasteland Panel -->
      <div class="w-full mb-8">
        <WastelandPanel />
      </div>

      <!-- Room Grid with Floating Build Button -->
      <div class="relative">
        <RoomGrid
          :selectedRoom="selectedRoom"
          :isPlacingRoom="isPlacingRoom"
          :incidents="activeIncidents"
          :highlightedRoomId="highlightedRoomId"
          @roomPlaced="handleRoomPlaced"
          @incidentClicked="handleIncidentClicked"
        />

        <!-- Floating Build Button -->
        <div class="floating-build-button">
          <BuildModeButton :buildModeActive="buildModeActive" @toggleBuildMode="toggleBuildMode" />
        </div>
      </div>

      <!-- Build Menu -->
      <RoomMenu
        v-if="showRoomMenu"
        @roomSelected="handleRoomSelected"
        @close="showRoomMenu = false"
      />
        </div>
      </div>
    </div>

    <!-- Combat Modal -->
    <CombatModal
      v-if="showCombatModal && selectedIncidentId && vaultId"
      :incidentId="selectedIncidentId"
      :vaultId="vaultId"
      @close="handleCombatModalClose"
      @resolved="handleIncidentResolved"
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

/* Floating Build Button */
.floating-build-button {
  position: absolute;
  top: 1rem;
  right: 1rem;
  z-index: 10;
  animation: subtlePulse 3s ease-in-out infinite;
}

@keyframes subtlePulse {
  0%, 100% {
    opacity: 0.95;
  }
  50% {
    opacity: 1;
  }
}
</style>
