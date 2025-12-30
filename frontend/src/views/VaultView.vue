<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useRoomStore } from '@/stores/room'
import { useVaultStore } from '@/stores/vault'
import { useDwellerStore } from '@/stores/dweller'
import { useExplorationStore } from '@/stores/exploration'
import RoomGrid from '@/components/rooms/RoomGrid.vue'
import BuildModeButton from '@/components/common/BuildModeButton.vue'
import RoomMenu from '@/components/rooms/RoomMenu.vue'
import ResourceBar from '@/components/common/ResourceBar.vue'
import GameControlPanel from '@/components/common/GameControlPanel.vue'
import UnassignedDwellers from '@/components/dwellers/UnassignedDwellers.vue'
import WastelandPanel from '@/components/wasteland/WastelandPanel.vue'
import type { Room } from '@/models/room'
import { Icon } from '@iconify/vue'

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
const showRoomMenu = ref(false)
const selectedRoom = ref<Room | null>(null)
const isPlacingRoom = ref(false)
const isLoading = ref(true)
const errorMessage = ref<string | null>(null)

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
      console.log('[VaultView] Loaded explorations:', explorationStore.explorations.length)
    } catch (error) {
      console.error('[VaultView] Failed to load explorations:', error)
      // Don't fail the whole page load if explorations fail
    }

    // Fetch game state and start polling
    try {
      await vaultStore.fetchGameState(id, authStore.token)
      if (!vaultStore.gameState?.is_paused) {
        vaultStore.startResourcePolling(id, authStore.token)
      }
    } catch (error) {
      console.warn('Game state not available, continuing without it', error)
    }

    isLoading.value = false
  } catch (error) {
    console.error('Failed to load vault:', error)
    errorMessage.value = error instanceof Error ? error.message : 'Failed to load vault data'
    isLoading.value = false
  }
}

// Watch for vault ID changes in the URL
watch(() => vaultId.value, (newId) => {
  if (newId) {
    vaultStore.stopResourcePolling()
    loadVaultData(newId)
  }
}, { immediate: true })

onMounted(async () => {
  // Initial load is handled by the watcher
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
    console.log(`Placing ${selectedRoom.value.name} at position ${JSON.stringify(position)}`)
    isPlacingRoom.value = false
    selectedRoom.value = null
  }
}
</script>

<template>
  <div class="relative min-h-screen bg-terminalBackground font-mono text-terminalGreen">
    <div class="scanlines"></div>

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
    <div
      v-else
      class="flicker container mx-auto flex flex-col items-center justify-center px-4 py-8 lg:px-8"
    >
      <!-- Game Control Panel -->
      <div v-if="vaultId" class="mb-4 w-full flex justify-center">
        <GameControlPanel :vaultId="vaultId" />
      </div>

      <div class="mb-8 flex w-full items-center justify-between space-x-8">
        <!-- Dwellers Count and Happiness -->
        <div class="flex items-center space-x-4">
          <div class="flex items-center space-x-2">
            <Icon icon="mdi:account-group" class="h-8 w-8 text-terminalGreen" />
            <p>{{ dwellersCount }}</p>
          </div>
          <div class="flex items-center space-x-2">
            <Icon icon="mdi:emoticon-happy" class="h-6 w-6 text-terminalGreen" />
            <p>{{ happiness }}%</p>
          </div>
        </div>

        <!-- Resources in the Middle -->
        <div class="flex justify-center space-x-8">
          <ResourceBar :current="energy.current" :max="energy.max" icon="mdi:lightning-bolt" />
          <ResourceBar :current="food.current" :max="food.max" icon="mdi:food-apple" />
          <ResourceBar :current="water.current" :max="water.max" icon="mdi:water" />
        </div>

        <!-- Bottle Caps and Build Button -->
        <div class="flex items-center space-x-4">
          <div class="flex items-center space-x-2">
            <Icon icon="mdi:currency-usd" class="h-6 w-6 text-terminalGreen" />
            <p>{{ bottleCaps }}</p>
          </div>
          <BuildModeButton :buildModeActive="buildModeActive" @toggleBuildMode="toggleBuildMode" />
        </div>
      </div>

      <!-- Unassigned Dwellers Panel -->
      <div class="w-full mb-4">
        <UnassignedDwellers />
      </div>

      <!-- Wasteland Panel -->
      <div class="w-full mb-8">
        <WastelandPanel />
      </div>

      <!-- Room Grid -->
      <RoomGrid
        :selectedRoom="selectedRoom"
        :isPlacingRoom="isPlacingRoom"
        @roomPlaced="handleRoomPlaced"
      />

      <!-- Build Menu -->
      <RoomMenu
        v-if="showRoomMenu"
        @roomSelected="handleRoomSelected"
        @close="showRoomMenu = false"
      />
    </div>
  </div>
</template>

<style scoped>
/* All styling handled by Tailwind utilities - no custom styles needed */
</style>
