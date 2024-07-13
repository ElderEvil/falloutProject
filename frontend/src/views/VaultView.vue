<script setup lang="ts">
import { useRoomStore } from '@/stores/room'
import RoomGrid from '@/components/RoomGrid.vue'
import { onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const roomStore = useRoomStore()

onMounted(async () => {
  const vaultId = localStorage.getItem('selectedVaultId')
  if (vaultId) {
    await roomStore.fetchRooms(vaultId, authStore.token as string)
  }
})
</script>

<template>
  <div class="relative min-h-screen bg-terminalBackground font-mono text-terminalGreen">
    <div class="scanlines"></div>
    <div
      class="flicker container mx-auto flex flex-col items-center justify-center px-4 py-8 lg:px-8"
    >
      <h1 class="mb-8 text-4xl font-bold">Vault Rooms</h1>
      <RoomGrid />
    </div>
  </div>
</template>

<style scoped>
/* Scoped styles here if needed */
</style>
