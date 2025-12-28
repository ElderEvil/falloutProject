<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useRoomStore } from '@/stores/room'
import RoomGrid from '@/components/rooms/RoomGrid.vue'
import BuildModeButton from '@/components/common/BuildModeButton.vue'
import RoomMenu from '@/components/rooms/RoomMenu.vue'
import type { Room } from '@/models/room'

interface Position {
  x: number
  y: number
}

const route = useRoute()
const authStore = useAuthStore()
const roomStore = useRoomStore()
const showRoomMenu = ref(false)
const selectedRoom = ref<Room | null>(null)
const isPlacingRoom = ref(false)

const buildModeActive = computed(() => showRoomMenu.value || isPlacingRoom.value)

onMounted(async () => {
  const vaultId = route.params.vaultId as string
  if (vaultId && authStore.token) {
    await roomStore.fetchRooms(vaultId, authStore.token)
  }
})

const toggleBuildMode = async () => {
  if (buildModeActive.value) {
    showRoomMenu.value = false
    isPlacingRoom.value = false
    selectedRoom.value = null
  } else {
    if (roomStore.availableRooms.length === 0 && authStore.token) {
      await roomStore.fetchRoomsData(authStore.token)
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
  <div class="relative">
    <!-- Build Mode Button -->
    <div class="flex justify-end mb-4">
      <BuildModeButton :buildModeActive="buildModeActive" @toggleBuildMode="toggleBuildMode" />
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
</template>
