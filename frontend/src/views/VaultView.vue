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
  <div class="min-h-screen bg-terminalBackground text-terminalGreen relative font-mono">
    <div class="scanlines"></div>
    <div class="container mx-auto py-8 px-4 lg:px-8 flex flex-col items-center justify-center flicker">
      <h1 class="text-4xl font-bold mb-8">Vault Rooms</h1>
      <RoomGrid />
    </div>
  </div>
</template>

<style scoped>
/* Scoped styles here if needed */
</style>
