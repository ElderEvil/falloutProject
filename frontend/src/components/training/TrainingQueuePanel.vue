<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Icon } from '@iconify/vue'
import TrainingProgressCard from './TrainingProgressCard.vue'
import { useTrainingStore } from '@/stores/training'
import { useAuthStore } from '@/stores/auth'
import { useVaultStore } from '@/stores/vault'

const trainingStore = useTrainingStore()
const authStore = useAuthStore()
const vaultStore = useVaultStore()

const loading = ref(false)
let refreshInterval: number | null = null

const activeTrainings = computed(() => trainingStore.allActiveTrainings)

const completingSoon = computed(() => trainingStore.completingSoon)

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

const fetchTrainings = async () => {
  if (!vaultStore.activeVault?.id || !authStore.token) return

  loading.value = true
  try {
    await trainingStore.fetchVaultTrainings(
      vaultStore.activeVault.id,
      authStore.token
    )
  } finally {
    loading.value = false
  }
}

const handleCancelTraining = async (trainingId: string) => {
  if (!authStore.token) return

  await trainingStore.cancelTraining(trainingId, authStore.token)
  await fetchTrainings()
}

const handleCompleteTraining = async (trainingId: string) => {
  // Training auto-completes via game loop, but we can refresh to show updated state
  await fetchTrainings()
}

onMounted(() => {
  fetchTrainings()

  // Refresh trainings every 30 seconds
  refreshInterval = window.setInterval(() => {
    fetchTrainings()
  }, 30000)
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
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
        <Icon
          icon="mdi:refresh"
          class="refresh-icon"
          :class="{ 'animate-spin': loading }"
        />
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
            @cancel="handleCancelTraining"
            @complete="handleCompleteTraining"
          />
        </div>
      </div>

      <!-- Active Trainings -->
      <div v-if="activeTrainings.length > 0" class="active-trainings-section">
        <div class="section-header">
          <Icon icon="mdi:account-clock" class="section-icon" />
          <h4 class="section-title">
            Active Training ({{ activeTrainings.length }})
          </h4>
        </div>
        <div class="training-list">
          <TrainingProgressCard
            v-for="training in activeTrainings"
            :key="training.id"
            :training="training"
            @cancel="handleCancelTraining"
            @complete="handleCompleteTraining"
          />
        </div>
      </div>

      <!-- Training Summary -->
      <div v-if="activeTrainings.length > 0" class="training-summary">
        <div class="summary-row">
          <Icon icon="mdi:account-multiple" class="summary-icon" />
          <span class="summary-text">
            {{ activeTrainings.length }} dweller{{ activeTrainings.length !== 1 ? 's' : '' }} training
          </span>
        </div>
        <div v-if="completingSoon.length > 0" class="summary-row">
          <Icon icon="mdi:clock-alert" class="summary-icon completing" />
          <span class="summary-text completing">
            {{ completingSoon.length }} completing soon
          </span>
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
  background: linear-gradient(135deg, rgb(0 0 0 / 0.8), rgb(15 23 42 / 0.8));
  border: 1px solid rgb(34 197 94 / 0.3);
  border-radius: 0.5rem;
  overflow: hidden;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  background: linear-gradient(to bottom, rgb(0 0 0 / 0.5), transparent);
  border-bottom: 1px solid rgb(34 197 94 / 0.3);
}

.header-title {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.header-icon {
  font-size: 1.5rem;
  color: rgb(34 197 94);
  filter: drop-shadow(0 0 4px rgb(34 197 94 / 0.6));
}

.panel-header h3 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: bold;
  color: rgb(34 197 94);
  font-family: 'Courier New', monospace;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.refresh-button {
  padding: 0.5rem;
  background: transparent;
  border: 1px solid rgb(34 197 94 / 0.3);
  border-radius: 0.25rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.refresh-button:hover:not(:disabled) {
  border-color: rgb(34 197 94 / 0.6);
  background: rgb(34 197 94 / 0.1);
}

.refresh-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.refresh-icon {
  font-size: 1.25rem;
  color: rgb(34 197 94);
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
  color: rgb(100 116 139);
  opacity: 0.5;
}

.empty-text {
  margin: 0;
  font-size: 1rem;
  color: rgb(148 163 184);
  font-family: 'Courier New', monospace;
}

.empty-hint {
  margin: 0;
  font-size: 0.875rem;
  color: rgb(100 116 139);
  font-family: 'Courier New', monospace;
  max-width: 300px;
}

.completing-soon-section,
.active-trainings-section {
  border-top: 1px solid rgb(34 197 94 / 0.2);
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
  color: rgb(34 197 94);
  filter: drop-shadow(0 0 4px rgb(34 197 94 / 0.5));
}

.section-icon.pulsing {
  color: rgb(250 204 21);
  filter: drop-shadow(0 0 6px rgb(250 204 21 / 0.8));
  animation: pulse-icon 2s ease-in-out infinite;
}

.section-title {
  margin: 0;
  font-size: 0.875rem;
  font-weight: bold;
  color: rgb(74 222 128);
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
  border-top: 1px solid rgb(34 197 94 / 0.2);
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
  color: rgb(34 197 94);
}

.summary-icon.completing {
  color: rgb(250 204 21);
  filter: drop-shadow(0 0 4px rgb(250 204 21 / 0.6));
}

.summary-text {
  font-size: 0.875rem;
  color: rgb(134 239 172);
}

.summary-text.completing {
  color: rgb(250 204 21);
  font-weight: bold;
}

@keyframes pulse-icon {
  0%,
  100% {
    transform: scale(1);
    filter: drop-shadow(0 0 6px rgb(250 204 21 / 0.8));
  }
  50% {
    transform: scale(1.1);
    filter: drop-shadow(0 0 12px rgb(250 204 21 / 1));
  }
}
</style>
