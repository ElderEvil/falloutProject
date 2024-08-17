<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useRoomStore } from '@/stores/room'
import { useVaultStore } from '@/stores/vault'
import RoomGrid from '@/components/rooms/RoomGrid.vue'
import BuildModeButton from '@/components/common/BuildModeButton.vue'
import RoomMenu from '@/components/rooms/RoomMenu.vue'
import ResourceBar from '@/components/common/ResourceBar.vue'

import { BoldIcon, FireIcon, BeakerIcon } from '@heroicons/vue/24/solid'

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
      <h1 class="mb-8 text-4xl font-bold">Vault Rooms</h1>

      <!-- Resources Display -->
      <div class="mb-4 flex w-full items-center justify-between space-x-4">
        <ResourceBar :current="energy.current" :max="energy.max" :icon="BoldIcon" />
        <ResourceBar :current="food.current" :max="food.max" :icon="FireIcon" />
        <ResourceBar :current="water.current" :max="water.max" :icon="BeakerIcon" />
      </div>

      <div class="mb-4 flex w-full items-center justify-between">
        <BuildModeButton :buildModeActive="buildModeActive" @toggleBuildMode="toggleBuildMode" />
      </div>
      <RoomGrid
        :selectedRoom="selectedRoom"
        :isPlacingRoom="isPlacingRoom"
        @roomPlaced="handleRoomPlaced"
      />
      <RoomMenu
        v-if="showRoomMenu"
        @roomSelected="handleRoomSelected"
        @close="showRoomMenu = false"
      />
    </div>
  </div>
</template>

<style scoped>
/* Scoped styles here if needed */
</style>
