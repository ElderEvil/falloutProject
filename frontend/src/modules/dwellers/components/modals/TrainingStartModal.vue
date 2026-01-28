<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import UModal from '@/core/components/ui/UModal.vue'
import UButton from '@/core/components/ui/UButton.vue'
import UAlert from '@/core/components/ui/UAlert.vue'
import { useTrainingStore } from '@/modules/progression/stores/training'
import { useRoomStore } from '@/modules/rooms/stores/room'
import { useAuthStore } from '@/modules/auth/stores/auth'
import type { components } from '@/core/types/api.generated'

type DwellerReadFull = components['schemas']['DwellerReadFull']

interface Props {
  modelValue: boolean
  dweller: DwellerReadFull
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'started'): void
}>()

const trainingStore = useTrainingStore()
const roomStore = useRoomStore()
const authStore = useAuthStore()

const selectedStat = ref<string | null>(null)
const loading = ref(false)

// Fetch rooms when modal opens
watch(() => props.modelValue, async (isOpen) => {
  if (isOpen && authStore.token && props.dweller.vault) {
    await roomStore.fetchRooms(props.dweller.vault.id, authStore.token)
  }
})

const stats = [
  { key: 'strength', label: 'Strength', short: 'S', icon: 'mdi:arm-flex', color: 'text-red-400' },
  { key: 'perception', label: 'Perception', short: 'P', icon: 'mdi:eye', color: 'text-blue-400' },
  { key: 'endurance', label: 'Endurance', short: 'E', icon: 'mdi:heart', color: 'text-orange-400' },
  { key: 'charisma', label: 'Charisma', short: 'C', icon: 'mdi:account-heart', color: 'text-pink-400' },
  { key: 'intelligence', label: 'Intelligence', short: 'I', icon: 'mdi:brain', color: 'text-purple-400' },
  { key: 'agility', label: 'Agility', short: 'A', icon: 'mdi:run-fast', color: 'text-green-400' },
  { key: 'luck', label: 'Luck', short: 'L', icon: 'mdi:clover', color: 'text-yellow-400' },
]

const availableStats = computed(() => {
  return stats.filter(stat => (props.dweller as any)[stat.short] < 10)
})

const selectedRoom = computed(() => {
  if (!selectedStat.value) return null
  const statKey = selectedStat.value.toLowerCase()

  const found = roomStore.rooms.find((room) => {
    const isTraining = room.category === 'training'
    const abilityMatch = room.ability?.toLowerCase() === statKey

    return isTraining && abilityMatch
  })

  return found
})

const canStart = computed(() => {
  return selectedStat.value !== null && selectedRoom.value !== null && !loading.value
})

const handleStart = async () => {
  if (!canStart.value || !authStore.token || !selectedRoom.value) return

  loading.value = true
  try {
    const result = await trainingStore.startTraining(
      props.dweller.id,
      selectedRoom.value.id,
      authStore.token
    )
    if (result) {
      emit('started')
      emit('update:modelValue', false)
    }
  } finally {
    loading.value = false
  }
}

const close = () => {
  emit('update:modelValue', false)
  selectedStat.value = null
}
</script>

<template>
  <UModal
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    title="Start Training"
    size="md"
    @close="close"
  >
    <div class="training-start-modal">
      <p class="description">
        Select a SPECIAL stat to improve for <span class="dweller-name">{{ dweller.first_name }} {{ dweller.last_name }}</span>.
      </p>

      <div class="stats-grid">
        <button
          v-for="stat in availableStats"
          :key="stat.key"
          class="stat-button"
          :class="{ 'selected': selectedStat === stat.key }"
          @click="selectedStat = stat.key"
        >
          <div class="stat-icon-wrapper" :class="stat.color">
            <Icon :icon="stat.icon" class="stat-icon" />
            <span class="stat-short">{{ stat.short }}</span>
          </div>
          <div class="stat-info">
            <span class="stat-label">{{ stat.label }}</span>
            <span class="stat-value">{{ (dweller as any)[stat.short] }}/10</span>
          </div>
        </button>
      </div>

      <div v-if="selectedStat" class="room-info-section">
        <template v-if="selectedRoom">
          <div class="room-found">
            <Icon icon="mdi:office-building" class="room-icon" />
            <div class="room-details">
              <span class="room-label">Training Room Found:</span>
              <span class="room-name">{{ selectedRoom.name }}</span>
            </div>
          </div>
        </template>
        <template v-else>
          <UAlert variant="error" class="no-room-alert">
            <Icon icon="mdi:alert-circle" class="h-5 w-5" />
            No training room available for {{ selectedStat }}. Build one first!
          </UAlert>
        </template>
      </div>

      <div class="modal-actions">
        <UButton variant="secondary" @click="close">Cancel</UButton>
        <UButton
          variant="primary"
          :disabled="!canStart"
          :loading="loading"
          @click="handleStart"
        >
          Start Training
        </UButton>
      </div>
    </div>
  </UModal>
</template>

<style scoped>
.training-start-modal {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.description {
  color: var(--color-theme-primary);
  opacity: 0.8;
  font-size: 0.875rem;
}

.dweller-name {
  font-weight: 700;
  color: var(--color-theme-primary);
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.75rem;
}

.stat-button {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid var(--color-theme-glow);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  text-align: left;
}

.stat-button:hover {
  background: rgba(0, 0, 0, 0.5);
  border-color: var(--color-theme-primary);
}

.stat-button.selected {
  background: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.1);
  border-color: var(--color-theme-primary);
  box-shadow: 0 0 10px var(--color-theme-glow);
}

.stat-icon-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  background: rgba(0, 0, 0, 0.4);
  border-radius: 4px;
  position: relative;
}

.stat-icon {
  font-size: 1.25rem;
}

.stat-short {
  font-size: 0.625rem;
  font-weight: 800;
  position: absolute;
  top: 1px;
  right: 2px;
  opacity: 0.7;
}

.stat-info {
  display: flex;
  flex-direction: column;
}

.stat-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--color-theme-primary);
  text-transform: uppercase;
}

.stat-value {
  font-size: 0.875rem;
  font-weight: 700;
  color: var(--color-theme-primary);
}

.room-info-section {
  padding: 1rem;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 6px;
  border: 1px solid rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.2);
}

.room-found {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.room-icon {
  font-size: 1.5rem;
  color: var(--color-theme-primary);
}

.room-details {
  display: flex;
  flex-direction: column;
}

.room-label {
  font-size: 0.75rem;
  color: var(--color-theme-primary);
  opacity: 0.7;
}

.room-name {
  font-weight: 700;
  color: var(--color-theme-primary);
}

.no-room-alert {
  margin: 0;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
  margin-top: 0.5rem;
}
</style>
