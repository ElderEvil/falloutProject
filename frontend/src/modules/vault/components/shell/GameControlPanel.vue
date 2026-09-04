<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useIncidentStore } from '@/modules/combat/stores/incident'
import { IncidentType } from '@/modules/combat/models/incident'
import { handleStoreError } from '@/core/utils/errorHandler'

const vaultStore = useVaultStore()
const authStore = useAuthStore()
const incidentStore = useIncidentStore()

const isSuperuser = computed(() => authStore.user?.is_superuser ?? false)

const props = defineProps<{
  vaultId: string
}>()

const isPaused = computed(() => vaultStore.gameState?.is_paused ?? false)
const isLoading = computed(() => vaultStore.isLoading)
const isSpawningIncident = ref(false)

const testIncidents = [
  { type: IncidentType.FIRE, label: 'Fire', icon: 'mdi:fire' },
  { type: IncidentType.RADROACH_INFESTATION, label: 'Radroach', icon: 'mdi:bug' },
  { type: IncidentType.MOLE_RAT_ATTACK, label: 'Mole Rat', icon: 'mdi:paw' },
  { type: IncidentType.RADSCORPION_ATTACK, label: 'Radscorpion', icon: 'mdi:spider' },
  { type: IncidentType.RAIDER_ATTACK, label: 'Raider', icon: 'mdi:skull' },
  { type: IncidentType.FERAL_GHOUL_ATTACK, label: 'Feral Ghoul', icon: 'mdi:ghost' },
  { type: IncidentType.DEATHCLAW_ATTACK, label: 'Deathclaw', icon: 'mdi:claw-mark' },
]

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
    handleStoreError(error, 'Failed to update vault pause state')
  }
}

const spawnIncident = async (type: IncidentType) => {
  if (!authStore.token || isSpawningIncident.value) return

  isSpawningIncident.value = true
  try {
    await incidentStore.spawnDebugIncident(props.vaultId, authStore.token, type)
  } catch (error) {
    handleStoreError(error, 'Failed to spawn incident')
  } finally {
    isSpawningIncident.value = false
  }
}

const initializeGameState = async () => {
  if (authStore.token) {
    try {
      await vaultStore.fetchGameState(props.vaultId, authStore.token)

      if (!isPaused.value) {
        vaultStore.startResourcePolling()
      }
    } catch (error) {
      handleStoreError(error, 'Failed to load game state')
    }
  }
}

onMounted(() => {
  void initializeGameState()
})

onUnmounted(() => {
  // Clean up polling when component unmounts
  vaultStore.stopResourcePolling()
})
</script>

<template>
  <div
    class="fixed bottom-4 right-4 z-50 flex min-w-0 max-w-[calc(100vw-2rem)] flex-wrap items-center gap-2 rounded border border-theme-primary/30 bg-surface-warm/90 px-4 py-2 shadow-lg"
  >
    <!-- Game Time -->
    <div class="flex shrink-0 items-center gap-2 text-theme-primary">
      <Icon icon="mdi:clock-outline" class="h-5 w-5" />
      <span class="font-mono text-sm">{{ totalGameTime }}</span>
    </div>

    <div class="game-control-actions flex min-w-0 flex-wrap items-center gap-2">
      <!-- Pause/Resume Button -->
      <button
        @click="togglePause"
        :disabled="isLoading"
        class="flex shrink-0 items-center gap-2 rounded px-3 py-1 transition-all duration-200"
        :class="{
          'bg-yellow-700 hover:bg-yellow-800': !isPaused && !isLoading,
          'bg-green-600 hover:bg-green-700': isPaused && !isLoading,
          'bg-gray-600 cursor-not-allowed': isLoading,
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
        class="flex shrink-0 items-center gap-2 rounded border border-yellow-600/50 bg-yellow-600/20 px-3 py-1"
      >
        <div class="h-2 w-2 rounded-full bg-yellow-500 animate-pulse"></div>
        <span class="text-xs font-semibold text-yellow-500">PAUSED</span>
      </div>

      <div v-if="isSuperuser" class="admin-incident-controls flex min-w-0 flex-wrap items-center gap-1">
        <span class="mr-1 text-xs font-semibold text-red-400">TEST INCIDENTS</span>
        <button
          v-for="incident in testIncidents"
          :key="incident.type"
          class="admin-incident-button flex shrink-0 items-center gap-1 rounded border border-red-500/50 px-2 py-1 text-xs font-semibold text-red-100 transition-colors hover:bg-red-700/60 disabled:cursor-not-allowed disabled:opacity-50"
          :disabled="isLoading || isSpawningIncident"
          :title="`Spawn ${incident.label} incident`"
          @click="spawnIncident(incident.type)"
        >
          <Icon :icon="incident.icon" class="h-3.5 w-3.5" />
          {{ incident.label }}
        </button>
      </div>
    </div>
  </div>
</template>
