<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import { Icon } from '@iconify/vue'
import { useVaultStore } from '@/stores/vault'
import { useAuthStore } from '@/stores/auth'

const vaultStore = useVaultStore()
const authStore = useAuthStore()

const props = defineProps<{
  vaultId: string
}>()

const isPaused = computed(() => vaultStore.gameState?.is_paused ?? false)
const isLoading = computed(() => vaultStore.isLoading)

const formatGameTime = (seconds: number): string => {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  return `${hours}h ${minutes}m`
}

const totalGameTime = computed(() => {
  if (vaultStore.gameState?.total_game_time) {
    return formatGameTime(vaultStore.gameState.total_game_time)
  }
  return '0h 0m'
})

const togglePause = async () => {
  if (!authStore.token) return

  try {
    if (isPaused.value) {
      await vaultStore.resumeVault(props.vaultId, authStore.token)
    } else {
      await vaultStore.pauseVault(props.vaultId, authStore.token)
    }
  } catch (error) {
    console.error('Failed to toggle pause', error)
  }
}

onMounted(async () => {
  if (authStore.token) {
    // Fetch initial game state
    await vaultStore.fetchGameState(props.vaultId, authStore.token)

    // Start resource polling if not paused
    if (!isPaused.value) {
      vaultStore.startResourcePolling(props.vaultId, authStore.token)
    }
  }
})

onUnmounted(() => {
  // Clean up polling when component unmounts
  vaultStore.stopResourcePolling()
})
</script>

<template>
  <div class="flex items-center space-x-4 rounded bg-gray-900/50 px-4 py-2 shadow-lg border border-terminalGreen/30">
    <!-- Game Time -->
    <div class="flex items-center space-x-2 text-terminalGreen">
      <Icon icon="mdi:clock-outline" class="h-5 w-5" />
      <span class="font-mono text-sm">{{ totalGameTime }}</span>
    </div>

    <!-- Pause/Resume Button -->
    <button
      @click="togglePause"
      :disabled="isLoading"
      class="flex items-center space-x-2 rounded px-3 py-1 transition-all duration-200"
      :class="{
        'bg-yellow-600 hover:bg-yellow-700': !isPaused && !isLoading,
        'bg-green-600 hover:bg-green-700': isPaused && !isLoading,
        'bg-gray-600 cursor-not-allowed': isLoading
      }"
      :title="isPaused ? 'Resume game' : 'Pause game'"
    >
      <Icon v-if="!isPaused" icon="mdi:pause" class="h-4 w-4 text-white" />
      <Icon v-else icon="mdi:play" class="h-4 w-4 text-white" />
      <span class="text-sm font-semibold text-white">
        {{ isPaused ? 'Resume' : 'Pause' }}
      </span>
    </button>

    <!-- Paused Indicator -->
    <div
      v-if="isPaused"
      class="flex items-center space-x-2 rounded bg-yellow-600/20 px-3 py-1 border border-yellow-600/50"
    >
      <div class="h-2 w-2 rounded-full bg-yellow-500 animate-pulse"></div>
      <span class="text-xs font-semibold text-yellow-500">PAUSED</span>
    </div>
  </div>
</template>
