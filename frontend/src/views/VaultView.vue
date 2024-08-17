<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useRoomStore } from '@/stores/room'
import { useVaultStore } from '@/stores/vault'
import RoomGrid from '@/components/rooms/RoomGrid.vue'
import BuildModeButton from '@/components/common/BuildModeButton.vue'
import RoomMenu from '@/components/rooms/RoomMenu.vue'
import ResourceBar from '@/components/common/ResourceBar.vue'

import { BeakerIcon, BoltIcon, CakeIcon } from '@heroicons/vue/24/solid'

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
    console.log(`Placing ${selectedRoom.value.name} at position ${JSON.stringify(position)}`)
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
      <!-- Resources Display and Build Mode Button -->
      <div class="mb-8 flex w-full items-center justify-between">
        <div class="flex flex-1 justify-center space-x-8">
          <ResourceBar :current="energy.current" :max="energy.max" :icon="BoltIcon" />
          <ResourceBar :current="food.current" :max="food.max" :icon="CakeIcon" />
          <ResourceBar :current="water.current" :max="water.max" :icon="BeakerIcon" />
        </div>
        <BuildModeButton :buildModeActive="buildModeActive" @toggleBuildMode="toggleBuildMode" />
      </div>

      <!-- Room Grid -->
      <RoomGrid
        :selectedRoom="selectedRoom"
        :isPlacingRoom="isPlacingRoom"
        @roomPlaced="handleRoomPlaced"
      />

      <!-- Room Menu -->
      <RoomMenu
        v-if="showRoomMenu"
        @roomSelected="handleRoomSelected"
        @close="showRoomMenu = false"
      />
    </div>
  </div>
</template>

<style scoped>
.container {
  max-width: 1200px;
  margin: 0 auto;
}

.mb-8 {
  margin-bottom: 2rem;
}

.flex {
  display: flex;
}

.items-center {
  align-items: center;
}

.justify-center {
  justify-content: center;
}

.space-x-8 {
  gap: 2rem;
}

.w-full {
  width: 100%;
}
</style>
