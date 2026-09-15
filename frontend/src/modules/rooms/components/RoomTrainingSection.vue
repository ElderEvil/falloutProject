<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Icon } from '@iconify/vue'
import type { Room } from '../models/room'
import type { DwellerShort, SpecialKey } from '@/modules/dwellers/models/dweller'
import type { components } from '@/core/types/api.generated'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useTrainingStore } from '@/modules/progression/stores/training'
import TrainingProgressCard from '@/modules/progression/components/training/TrainingProgressCard.vue'
import { getTrainingRoomCapacity } from '../utils/room'

type TrainingRead = components['schemas']['TrainingRead']

interface Props {
  room: Room
  assignedDwellers: DwellerShort[]
}

const props = defineProps<Props>()

const authStore = useAuthStore()
const trainingStore = useTrainingStore()

const trainings = ref<TrainingRead[]>([])
const isLoading = ref(false)
const busyDwellerId = ref<string | null>(null)

const roomToken = computed(() => (typeof authStore.token === 'string' ? authStore.token : null))
const capacity = computed(() => getTrainingRoomCapacity(props.room))
const activeTrainings = computed(() => trainings.value.filter((t) => t.status === 'active'))
const activeDwellerIds = computed(() => new Set(activeTrainings.value.map((t) => t.dweller_id)))
const canStartMore = computed(() => activeTrainings.value.length < capacity.value)

const statValue = (dweller: DwellerShort): number => {
  if (!props.room.ability) return 0
  const value = dweller[props.room.ability.toLowerCase() as SpecialKey]
  return typeof value === 'number' ? value : 0
}

const eligibleDwellers = computed(() =>
  props.assignedDwellers.filter(
    (dweller) =>
      !activeDwellerIds.value.has(dweller.id) &&
      statValue(dweller) < 10 &&
      ['idle', 'working', 'resting'].includes(dweller.status)
  )
)

const dwellerName = (dwellerId: string): string => {
  const dweller = props.assignedDwellers.find((d) => d.id === dwellerId)
  return dweller ? `${dweller.first_name} ${dweller.last_name ?? ''}`.trim() : 'Dweller'
}

const refresh = async () => {
  const token = roomToken.value
  if (!token) return
  isLoading.value = true
  try {
    trainings.value = await trainingStore.fetchRoomTrainings(props.room.id, token)
  } finally {
    isLoading.value = false
  }
}

const handleStart = async (dwellerId: string) => {
  const token = roomToken.value
  if (!token || busyDwellerId.value) return
  busyDwellerId.value = dwellerId
  try {
    await trainingStore.startTraining(dwellerId, props.room.id, token)
    await refresh()
  } finally {
    busyDwellerId.value = null
  }
}

const handleCancel = async (trainingId: string) => {
  const token = roomToken.value
  if (!token) return
  await trainingStore.cancelTraining(trainingId, token)
  await refresh()
}

const handleComplete = async (trainingId: string) => {
  const token = roomToken.value
  if (!token) return
  await trainingStore.completeTraining(trainingId, token)
  await refresh()
}

onMounted(() => {
  void refresh()
})
</script>

<template>
  <section class="section" aria-label="Training progress">
    <h3 class="section-title">
      <Icon icon="mdi:dumbbell" class="h-5 w-5" />
      Training ({{ activeTrainings.length }}/{{ capacity }})
    </h3>

    <p v-if="isLoading && !activeTrainings.length" class="section-empty">Loading training…</p>

    <div v-if="activeTrainings.length" class="training-list">
      <TrainingProgressCard
        v-for="training in activeTrainings"
        :key="training.id"
        :training="training"
        :dweller-name="dwellerName(training.dweller_id)"
        @cancel="handleCancel"
        @complete="handleComplete"
      />
    </div>
    <p v-else-if="!isLoading" class="section-empty">No dwellers training right now</p>

    <div v-if="canStartMore && eligibleDwellers.length" class="trainee-picker">
      <button
        v-for="dweller in eligibleDwellers"
        :key="dweller.id"
        type="button"
        class="trainee-option"
        :disabled="busyDwellerId !== null"
        @click="handleStart(dweller.id)"
      >
        <span class="trainee-name">{{ dweller.first_name }} {{ dweller.last_name }}</span>
        <span class="trainee-stat">{{ room.ability?.charAt(0) }} {{ statValue(dweller) }} → {{ statValue(dweller) + 1 }}</span>
      </button>
    </div>
  </section>
</template>

<style scoped>
.section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin: 0;
  color: var(--color-theme-primary);
  font-size: 0.875rem;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.section-title :deep(svg) {
  width: 0.875rem;
  height: 0.875rem;
}

.section-empty {
  margin: 0;
  font-size: 0.75rem;
  color: var(--color-gray-400);
}

.training-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.trainee-picker {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.trainee-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--color-theme-glow);
  border-radius: 4px;
  background: var(--color-surface-sunken);
  color: inherit;
  font: inherit;
  cursor: pointer;
}

.trainee-option:hover:not(:disabled),
.trainee-option:focus-visible {
  border-color: var(--color-theme-primary);
  background: var(--color-surface-hover);
  outline: none;
}

.trainee-option:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.trainee-name {
  font-weight: 600;
  font-size: 0.875rem;
  color: var(--color-theme-primary);
}

.trainee-stat {
  font-size: 0.75rem;
  color: var(--color-warning);
  font-weight: 700;
}
</style>
