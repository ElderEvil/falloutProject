<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useRoomStore } from '@/stores/room'
import { useVaultStore } from '@/stores/vault'
import RoomGrid from '@/components/rooms/RoomGrid.vue'
import BuildModeButton from '@/components/common/BuildModeButton.vue'
import RoomMenu from '@/components/rooms/RoomMenu.vue'
import ResourceBar from '@/components/common/ResourceBar.vue'
import type { Room } from '@/models/room'

import {
  CogIcon,
  FaceSmileIcon,
  BoltIcon,
  CakeIcon,
  BeakerIcon,
  CurrencyDollarIcon
} from '@heroicons/vue/24/solid'

interface Position {
  x: number
  y: number
}

const authStore = useAuthStore()
const roomStore = useRoomStore()
const vaultStore = useVaultStore()
const showRoomMenu = ref(false)
const selectedRoom = ref<Room | null>(null)
const isPlacingRoom = ref(false)

const buildModeActive = computed(() => showRoomMenu.value || isPlacingRoom.value)

const bottleCaps = computed(() => vaultStore.selectedVault?.bottle_caps ?? 0)
const dwellersCount = computed(() => vaultStore.selectedVault?.dweller_count ?? 0)
const happiness = computed(() => vaultStore.selectedVault?.happiness ?? 0)

const energy = computed(() => ({
  current: vaultStore.selectedVault?.power ?? 0,
  max: vaultStore.selectedVault?.power_max ?? 100
}))
const food = computed(() => ({
  current: vaultStore.selectedVault?.food ?? 0,
  max: vaultStore.selectedVault?.food_max ?? 100
}))
const water = computed(() => ({
  current: vaultStore.selectedVault?.water ?? 0,
  max: vaultStore.selectedVault?.water_max ?? 100
}))

onMounted(async () => {
  const vaultId = localStorage.getItem('selectedVaultId')
  if (vaultId) {
    await roomStore.fetchRooms(vaultId, authStore.token as string)
    await vaultStore.fetchVaults(authStore.token as string)
  }
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
    console.log(`Placing ${selectedRoom.value.number} at position ${JSON.stringify(position)}`)
    isPlacingRoom.value = false
    selectedRoom.value = null
  }
}
</script>

<template>
  <div class="relative min-h-screen bg-terminalBackground font-mono text-terminalGreen">
    <div class="scanlines"></div>

    <div
      class="flicker container mx-auto flex flex-col items-center justify-center px-4 py-8 lg:px-8"
    >
      <div class="mb-8 flex w-full items-center justify-between space-x-8">
        <!-- Dwellers Count and Happiness -->
        <div class="flex items-center space-x-4">
          <div class="flex items-center space-x-2">
            <CogIcon class="h-8 w-8 text-terminalGreen" />
            <p>{{ dwellersCount }}</p>
          </div>
          <div class="flex items-center space-x-2">
            <FaceSmileIcon class="h-6 w-6 text-terminalGreen" />
            <p>{{ happiness }}%</p>
          </div>
        </div>

        <!-- Resources in the Middle -->
        <div class="flex justify-center space-x-8">
          <ResourceBar :current="energy.current" :max="energy.max" :icon="BoltIcon" />
          <ResourceBar :current="food.current" :max="food.max" :icon="CakeIcon" />
          <ResourceBar :current="water.current" :max="water.max" :icon="BeakerIcon" />
        </div>

        <!-- Bottle Caps and Build Button -->
        <div class="flex items-center space-x-4">
          <div class="flex items-center space-x-2">
            <CurrencyDollarIcon class="h-6 w-6 text-terminalGreen" />
            <p>{{ bottleCaps }}</p>
          </div>
          <BuildModeButton :buildModeActive="buildModeActive" @toggleBuildMode="toggleBuildMode" />
        </div>
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
