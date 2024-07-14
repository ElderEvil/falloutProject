<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useRoomStore } from '@/stores/room'
import RoomGrid from '@/components/RoomGrid.vue'
import HammerIcon from '@/components/icons/HammerIcon.vue'
import RoomMenu from '@/components/RoomMenu.vue'

const authStore = useAuthStore()
const roomStore = useRoomStore()
const showRoomMenu = ref(false)
const selectedRoom = ref(null)

onMounted(async () => {
  const vaultId = localStorage.getItem('selectedVaultId')
  if (vaultId) {
    await roomStore.fetchRooms(vaultId, authStore.token as string)
  }
})

const toggleRoomMenu = async () => {
  if (roomStore.availableRooms.length === 0) {
    await roomStore.fetchRoomsData(authStore.token as string)
  }
  showRoomMenu.value = !showRoomMenu.value
}

const handleRoomSelected = (room) => {
  selectedRoom.value = room
  showRoomMenu.value = false
}
</script>

<template>
  <div class="relative min-h-screen bg-terminalBackground font-mono text-terminalGreen">
    <div class="scanlines"></div>
    <div
      class="flicker container mx-auto flex flex-col items-center justify-center px-4 py-8 lg:px-8"
    >
      <h1 class="mb-8 text-4xl font-bold">Vault Rooms</h1>
      <div class="mb-4 flex w-full items-center justify-between">
        <button @click="toggleRoomMenu" class="flex items-center rounded bg-gray-700 px-4 py-2">
          <HammerIcon />
          <span class="ml-2">{{ showRoomMenu ? 'Close Room Menu' : 'Build Mode' }}</span>
        </button>
      </div>
      <RoomGrid :selectedRoom="selectedRoom" />
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
