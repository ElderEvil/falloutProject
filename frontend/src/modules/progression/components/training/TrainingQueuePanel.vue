<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { useTrainingStore } from '@/modules/progression/stores/training'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useDwellerFilterStore } from '@/modules/dwellers/stores/dwellerFilter'
import { useRoomStore } from '@/modules/rooms/stores/room'
import { usePolling } from '@/core/composables/usePolling'
import TrainingProgressCard from './TrainingProgressCard.vue'

const trainingStore = useTrainingStore()
const authStore = useAuthStore()
const vaultStore = useVaultStore()
const dwellerStore = useDwellerFilterStore()
const roomStore = useRoomStore()

const loading = ref(false)

const activeTrainings = computed(() => trainingStore.allActiveTrainings)

const completingSoon = computed(() => trainingStore.completingSoon)

const dwellerLookup = computed(() => {
  const lookup = new Map<string, { name: string; image: string | null }>()
  for (const dweller of dwellerStore.dwellers) {
    lookup.set(dweller.id, {
      name: `${dweller.first_name} ${dweller.last_name ?? ''}`.trim(),
      image: dweller.thumbnail_url ?? null,
    })
  }
  return lookup
})

const roomLookup = computed(() => {
  const lookup = new Map<string, string>()
  for (const room of roomStore.rooms) {
    lookup.set(room.id, room.name)
  }
  return lookup
})

const getDweller = (dwellerId: string) => dwellerLookup.value.get(dwellerId)

const getRoomName = (roomId: string) => roomLookup.value.get(roomId) ?? 'Training Room'

const groupedByRoom = computed(() => {
  const groups: Record<string, typeof activeTrainings.value> = {}

  activeTrainings.value.forEach((training) => {
    const roomId = training.room_id
    if (!groups[roomId]) {
      groups[roomId] = []
    }
    groups[roomId].push(training)
  })

  return groups
})

const roomGroups = computed(() => {
  return Object.entries(groupedByRoom.value).map(([roomId, trainings]) => ({
    roomId,
    roomName: getRoomName(roomId),
    trainings,
  }))
})

const fetchTrainings = async () => {
  if (!vaultStore.activeVault?.id || !authStore.token) return

  loading.value = true
  try {
    await Promise.all([
      trainingStore.fetchVaultTrainings(vaultStore.activeVault.id, authStore.token),
      dwellerStore.fetchDwellersByVault(vaultStore.activeVault.id, authStore.token),
      roomStore.fetchRooms(vaultStore.activeVault.id, authStore.token),
    ])
  } finally {
    loading.value = false
  }
}

// Refresh trainings every 30 seconds while this panel is mounted.
usePolling(fetchTrainings, { interval: 30_000, immediate: false })

const handleCancelTraining = async (trainingId: string) => {
  if (!authStore.token) return

  await trainingStore.cancelTraining(trainingId, authStore.token)
  await fetchTrainings()
}

const handleCompleteTraining = async (trainingId: string) => {
  if (!authStore.token) return

  await trainingStore.completeTraining(trainingId, authStore.token)
  await fetchTrainings()
}

onMounted(() => {
  // Fetch when vault becomes available (handles page reload where vault loads async)
  watch(
    () => vaultStore.activeVault?.id,
    (newId) => {
      if (newId && authStore.token) {
        fetchTrainings()
      }
    },
    { immediate: true }
  )
})
</script>

<template>
  <div class="training-queue-panel">
    <div class="panel-header">
      <div class="header-title">
        <Icon icon="mdi:dumbbell" class="header-icon" />
        <h3>Training Queue</h3>
      </div>
      <button @click="fetchTrainings" class="refresh-button" :disabled="loading">
        <Icon icon="mdi:refresh" class="refresh-icon" :class="{ 'animate-spin': loading }" />
      </button>
    </div>

    <div class="panel-content">
      <!-- Empty State -->
      <div v-if="activeTrainings.length === 0" class="empty-state">
        <Icon icon="mdi:sleep" class="empty-icon" />
        <p class="empty-text">No dwellers currently training</p>
        <p class="empty-hint">Assign dwellers to training rooms to improve their SPECIAL stats</p>
      </div>

      <!-- Completing Soon Section -->
      <div v-if="completingSoon.length > 0" class="completing-soon-section">
        <div class="section-header">
          <Icon icon="mdi:clock-fast" class="section-icon pulsing" />
          <h4 class="section-title">Completing Soon ({{ completingSoon.length }})</h4>
        </div>
        <div class="training-list">
          <TrainingProgressCard
            v-for="training in completingSoon"
            :key="training.id"
            :training="training"
            :dweller-name="getDweller(training.dweller_id)?.name"
            :dweller-image="getDweller(training.dweller_id)?.image"
            @cancel="handleCancelTraining"
            @complete="handleCompleteTraining"
          />
        </div>
      </div>

      <!-- Active Trainings grouped by room -->
      <div v-if="activeTrainings.length > 0" class="active-trainings-section">
        <div class="section-header">
          <Icon icon="mdi:account-clock" class="section-icon" />
          <h4 class="section-title">Active Training ({{ activeTrainings.length }})</h4>
        </div>
        <div v-for="group in roomGroups" :key="group.roomId" class="mb-4 flex flex-col gap-3">
          <div
            class="flex items-center gap-2 rounded border border-theme-glow bg-black/30 px-2 py-1.5"
          >
            <Icon
              icon="mdi:office-building"
              class="text-base text-theme-primary [filter:drop-shadow(0_0_4px_var(--color-theme-glow))]"
            />
            <span
              class="flex-1 font-mono text-xs font-bold uppercase tracking-[0.05em] text-theme-primary"
              >{{ group.roomName }}</span
            >
            <span class="font-mono text-xs font-bold text-theme-accent">{{
              group.trainings.length
            }}</span>
          </div>
          <div class="training-list">
            <TrainingProgressCard
              v-for="training in group.trainings"
              :key="training.id"
              :training="training"
              :dweller-name="getDweller(training.dweller_id)?.name"
              :dweller-image="getDweller(training.dweller_id)?.image"
              @cancel="handleCancelTraining"
              @complete="handleCompleteTraining"
            />
          </div>
        </div>
      </div>

      <!-- Training Summary -->
      <div v-if="activeTrainings.length > 0" class="training-summary">
        <div class="summary-row">
          <Icon icon="mdi:account-multiple" class="summary-icon" />
          <span class="summary-text">
            {{ activeTrainings.length }} dweller{{ activeTrainings.length !== 1 ? 's' : '' }}
            training
          </span>
        </div>
        <div v-if="completingSoon.length > 0" class="summary-row">
          <Icon icon="mdi:clock-alert" class="summary-icon completing" />
          <span class="summary-text completing"> {{ completingSoon.length }} completing soon </span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.training-queue-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: transparent;
  border: 2px solid var(--color-theme-primary);
  border-radius: 0.5rem;
  overflow: hidden;
  box-shadow: 0 0 10px var(--color-theme-glow);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  background: linear-gradient(to bottom, rgba(0, 0, 0, 0.5), transparent);
  border-bottom: 1px solid var(--color-theme-glow);
}

.header-title {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.header-icon {
  font-size: 1.5rem;
  color: var(--color-theme-primary);
  filter: drop-shadow(0 0 4px var(--color-theme-glow));
}

.panel-header h3 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: bold;
  color: var(--color-theme-primary);
  font-family: 'Courier New', monospace;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.refresh-button {
  padding: 0.5rem;
  background: transparent;
  border: 1px solid var(--color-theme-glow);
  border-radius: 0.25rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.refresh-button:hover:not(:disabled) {
  border-color: var(--color-theme-primary);
  background: var(--color-theme-glow);
}

.refresh-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.refresh-icon {
  font-size: 1.25rem;
  color: var(--color-theme-primary);
}

.panel-content {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 3rem 1.5rem;
  text-align: center;
}

.empty-icon {
  font-size: 4rem;
  color: var(--color-theme-primary);
  opacity: 0.3;
}

.empty-text {
  margin: 0;
  font-size: 1rem;
  color: var(--color-theme-primary);
  opacity: 0.6;
  font-family: 'Courier New', monospace;
}

.empty-hint {
  margin: 0;
  font-size: 0.875rem;
  color: var(--color-theme-primary);
  opacity: 0.5;
  font-family: 'Courier New', monospace;
  max-width: 300px;
}

.completing-soon-section,
.active-trainings-section {
  border-top: 1px solid var(--color-theme-glow);
  padding-top: 1rem;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.section-icon {
  font-size: 1.25rem;
  color: var(--color-theme-primary);
  filter: drop-shadow(0 0 4px var(--color-theme-glow));
}

.section-icon.pulsing {
  color: var(--color-theme-accent);
  filter: drop-shadow(0 0 6px var(--color-theme-accent));
  animation: pulse-icon 2s ease-in-out infinite;
}

.section-title {
  margin: 0;
  font-size: 0.875rem;
  font-weight: bold;
  color: var(--color-theme-primary);
  font-family: 'Courier New', monospace;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.training-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.training-summary {
  margin-top: auto;
  padding-top: 1rem;
  border-top: 1px solid var(--color-theme-glow);
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.summary-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-family: 'Courier New', monospace;
}

.summary-icon {
  font-size: 1rem;
  color: var(--color-theme-primary);
}

.summary-icon.completing {
  color: var(--color-theme-accent);
  filter: drop-shadow(0 0 4px var(--color-theme-accent));
}

.summary-text {
  font-size: 0.875rem;
  color: var(--color-theme-primary);
  opacity: 0.85;
}

.summary-text.completing {
  color: var(--color-theme-accent);
  font-weight: bold;
}

@keyframes pulse-icon {
  0%,
  100% {
    transform: scale(1);
    filter: drop-shadow(0 0 6px var(--color-theme-accent));
  }
  50% {
    transform: scale(1.1);
    filter: drop-shadow(0 0 12px var(--color-theme-accent));
  }
}
</style>
