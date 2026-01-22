<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import UModal from '@/core/components/ui/UModal.vue'
import UButton from '@/core/components/ui/UButton.vue'
import UAlert from '@/core/components/ui/UAlert.vue'
import TrainingProgressCard from './TrainingProgressCard.vue'
import { useTrainingStore } from '@/stores/training'
import { useAuthStore } from '@/modules/auth/stores/auth'
import type { components } from '@/core/types/api.generated'

type Room = any // You can type this properly based on your Room type
type Dweller = any // You can type this properly based on your Dweller type
type TrainingRead = components['schemas']['TrainingRead']

interface Props {
  modelValue: boolean
  room: Room | null
  dwellers?: Dweller[]
}

const props = withDefaults(defineProps<Props>(), {
  dwellers: () => []
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'close'): void
  (e: 'refresh'): void
}>()

const trainingStore = useTrainingStore()
const authStore = useAuthStore()

const loading = ref(false)
const activeTrainings = ref<TrainingRead[]>([])

const speedBonus = computed(() => {
  if (!props.room) return 0
  const tierMultipliers: Record<number, number> = { 1: 0, 2: 25, 3: 40 }
  return tierMultipliers[props.room.tier] || 0
})

const canStartMore = computed(() => {
  if (!props.room) return false
  return activeTrainings.value.length < props.room.capacity
})

const availableDwellers = computed(() => {
  if (!props.room || !props.dwellers) return []

  const trainingStat = props.room.ability?.toLowerCase()
  if (!trainingStat) return []

  return props.dwellers.filter((dweller: Dweller) => {
    // Check if dweller is assigned to this room
    if (dweller.room_id !== props.room?.id) return false

    // Check if dweller is already training
    if (trainingStore.isDwellerTraining(dweller.id)) return false

    // Check if stat is not maxed (assuming 10 is max)
    const statValue = dweller[trainingStat]
    if (statValue >= 10) return false

    // Check dweller status (must be idle or working)
    if (dweller.status !== 'idle' && dweller.status !== 'working') return false

    return true
  })
})

const getDwellerName = (dwellerId: string): string => {
  const dweller = props.dwellers.find((d: Dweller) => d.id === dwellerId)
  return dweller ? `${dweller.first_name} ${dweller.last_name}` : 'Unknown'
}

const close = () => {
  emit('update:modelValue', false)
  emit('close')
}

const fetchRoomTrainings = async () => {
  if (!props.room?.id || !authStore.token) return

  loading.value = true
  try {
    const trainings = await trainingStore.fetchRoomTrainings(
      props.room.id,
      authStore.token
    )
    activeTrainings.value = trainings.filter(t => t.status === 'active')
  } finally {
    loading.value = false
  }
}

const handleStartTraining = async (dwellerId: string) => {
  if (!props.room?.id || !authStore.token) return

  loading.value = true
  try {
    const result = await trainingStore.startTraining(
      dwellerId,
      props.room.id,
      authStore.token
    )

    if (result) {
      await fetchRoomTrainings()
      emit('refresh')
    }
  } finally {
    loading.value = false
  }
}

const handleCancelTraining = async (trainingId: string) => {
  if (!authStore.token) return

  loading.value = true
  try {
    const success = await trainingStore.cancelTraining(trainingId, authStore.token)
    if (success) {
      await fetchRoomTrainings()
      emit('refresh')
    }
  } finally {
    loading.value = false
  }
}

// Fetch trainings when modal opens
watch(() => props.modelValue, (isOpen) => {
  if (isOpen && props.room) {
    fetchRoomTrainings()
  }
}, { immediate: true })
</script>

<template>
  <UModal
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    @close="close"
    size="lg"
    :title="room ? `${room.name} - Training Room` : 'Training Room'"
  >
    <div v-if="room" class="training-modal">
      <!-- Room Info -->
      <div class="room-info">
        <div class="info-row">
          <Icon icon="mdi:dumbbell" class="info-icon" />
          <div class="info-content">
            <span class="info-label">Trains</span>
            <span class="info-value">{{ room.ability?.toUpperCase() }}</span>
          </div>
        </div>

        <div class="info-row">
          <Icon icon="mdi:account-group" class="info-icon" />
          <div class="info-content">
            <span class="info-label">Capacity</span>
            <span class="info-value">
              {{ activeTrainings.length }} / {{ room.capacity }}
            </span>
          </div>
        </div>

        <div class="info-row">
          <Icon icon="mdi:speedometer" class="info-icon" />
          <div class="info-content">
            <span class="info-label">Tier {{ room.tier }}</span>
            <span class="info-value" v-if="speedBonus > 0">
              {{ speedBonus }}% faster training
            </span>
            <span class="info-value" v-else>Normal speed</span>
          </div>
        </div>
      </div>

      <!-- Active Trainees -->
      <div v-if="activeTrainings.length > 0" class="active-trainees">
        <h4 class="section-title">
          <Icon icon="mdi:account-clock" class="section-icon" />
          Currently Training ({{ activeTrainings.length }})
        </h4>
        <div class="training-list">
          <TrainingProgressCard
            v-for="training in activeTrainings"
            :key="training.id"
            :training="training"
            :dweller-name="getDwellerName(training.dweller_id)"
            @cancel="handleCancelTraining"
          />
        </div>
      </div>

      <!-- Available Dwellers -->
      <div v-if="canStartMore" class="available-dwellers">
        <h4 class="section-title">
          <Icon icon="mdi:account-plus" class="section-icon" />
          Assign Dweller to Train
        </h4>

        <div v-if="availableDwellers.length === 0" class="empty-state">
          <Icon icon="mdi:account-alert" class="empty-icon" />
          <p>No eligible dwellers available</p>
          <p class="empty-hint">
            Assign dwellers to this room and ensure their {{ room.ability }} stat is not maxed
          </p>
        </div>

        <div v-else class="dweller-list">
          <button
            v-for="dweller in availableDwellers"
            :key="dweller.id"
            @click="handleStartTraining(dweller.id)"
            class="dweller-option"
            :disabled="loading"
          >
            <div class="dweller-info">
              <span class="dweller-name">
                {{ dweller.first_name }} {{ dweller.last_name }}
              </span>
              <span class="dweller-level">Lvl {{ dweller.level }}</span>
            </div>
            <div class="dweller-stat">
              <span class="stat-label">{{ room.ability?.toUpperCase() }}</span>
              <span class="stat-value">{{ dweller[room.ability?.toLowerCase()] }}</span>
            </div>
          </button>
        </div>
      </div>

      <!-- Capacity Full Message -->
      <UAlert v-else variant="warning" class="capacity-alert">
        <Icon icon="mdi:alert" class="h-5 w-5" />
        Training room at full capacity. Wait for current training to complete or cancel one.
      </UAlert>

      <!-- Close Button -->
      <div class="modal-actions">
        <UButton variant="secondary" block @click="close">
          Close
        </UButton>
      </div>
    </div>
  </UModal>
</template>

<style scoped>
.training-modal {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.room-info {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
  padding: 1rem;
  background: linear-gradient(135deg, rgb(0 0 0 / 0.5), rgb(15 23 42 / 0.5));
  border: 1px solid rgb(34 197 94 / 0.3);
  border-radius: 0.5rem;
}

.info-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.info-icon {
  font-size: 1.5rem;
  color: rgb(34 197 94);
  filter: drop-shadow(0 0 4px rgb(34 197 94 / 0.5));
}

.info-content {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.info-label {
  font-size: 0.75rem;
  color: rgb(74 222 128);
  font-family: 'Courier New', monospace;
  text-transform: uppercase;
}

.info-value {
  font-size: 0.875rem;
  font-weight: bold;
  color: rgb(134 239 172);
  font-family: 'Courier New', monospace;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1rem;
  font-weight: bold;
  color: rgb(34 197 94);
  font-family: 'Courier New', monospace;
  text-transform: uppercase;
  margin-bottom: 0.75rem;
  letter-spacing: 0.05em;
}

.section-icon {
  font-size: 1.25rem;
  filter: drop-shadow(0 0 4px rgb(34 197 94 / 0.5));
}

.active-trainees {
  border-top: 1px solid rgb(34 197 94 / 0.2);
  padding-top: 1rem;
}

.training-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.available-dwellers {
  border-top: 1px solid rgb(34 197 94 / 0.2);
  padding-top: 1rem;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 2rem;
  background: rgb(0 0 0 / 0.3);
  border: 1px dashed rgb(100 116 139 / 0.5);
  border-radius: 0.5rem;
  text-align: center;
}

.empty-icon {
  font-size: 3rem;
  color: rgb(100 116 139);
}

.empty-state p {
  margin: 0;
  color: rgb(148 163 184);
  font-family: 'Courier New', monospace;
}

.empty-hint {
  font-size: 0.875rem;
  color: rgb(100 116 139);
  max-width: 300px;
}

.dweller-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  max-height: 300px;
  overflow-y: auto;
}

.dweller-option {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  background: linear-gradient(135deg, rgb(0 0 0 / 0.6), rgb(15 23 42 / 0.6));
  border: 1px solid rgb(34 197 94 / 0.3);
  border-radius: 0.375rem;
  cursor: pointer;
  transition: all 0.2s ease;
  font-family: 'Courier New', monospace;
}

.dweller-option:hover:not(:disabled) {
  border-color: rgb(34 197 94 / 0.6);
  background: linear-gradient(135deg, rgb(0 0 0 / 0.7), rgb(15 23 42 / 0.7));
  box-shadow: 0 0 10px rgb(34 197 94 / 0.3);
  transform: translateX(4px);
}

.dweller-option:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.dweller-info {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.dweller-name {
  font-size: 0.875rem;
  font-weight: bold;
  color: rgb(134 239 172);
}

.dweller-level {
  font-size: 0.75rem;
  color: rgb(74 222 128);
}

.dweller-stat {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.25rem;
}

.stat-label {
  font-size: 0.75rem;
  color: rgb(74 222 128);
  text-transform: uppercase;
}

.stat-value {
  font-size: 1.25rem;
  font-weight: bold;
  color: rgb(250 204 21);
  text-shadow: 0 0 4px rgb(250 204 21 / 0.6);
}

.capacity-alert {
  margin: 0;
}

.modal-actions {
  border-top: 1px solid rgb(34 197 94 / 0.2);
  padding-top: 1rem;
}
</style>
