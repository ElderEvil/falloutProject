<script setup lang="ts">
import { computed } from 'vue'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import RoomDwellerCard from './RoomDwellerCard.vue'

interface Props {
  ability: string | null
}

const props = defineProps<Props>()

const emit = defineEmits<{
  assignDweller: [dwellerId: string]
}>()

const { filter: dwellerStore } = useDwellerStore()
type AssignmentMode = 'worker' | 'apprentice'

const assignmentMode = defineModel<AssignmentMode | null>('assignmentMode', { default: null })

const availableDwellers = computed(() =>
  dwellerStore.dwellers
    .filter(
      (dweller) =>
        !dweller.room_id &&
        !['dead', 'questing', 'exploring'].includes(dweller.status) &&
        (assignmentMode.value === 'apprentice' ? dweller.age_group !== 'adult' : dweller.age_group === 'adult')
    )
    .sort((a, b) => `${a.first_name} ${a.last_name}`.localeCompare(`${b.first_name} ${b.last_name}`))
)

const pickDweller = (dwellerId: string) => {
  assignmentMode.value = null
  emit('assignDweller', dwellerId)
}

const pickerTitle = computed(() => (assignmentMode.value === 'apprentice' ? 'Select Apprentice' : 'Select Worker'))
</script>

<template>
  <div v-if="assignmentMode" class="dweller-picker">
    <div class="picker-header">
      <span class="picker-title">{{ pickerTitle }}</span>
      <button type="button" class="picker-close" aria-label="Close picker" @click="assignmentMode = null">×</button>
    </div>
    <RoomDwellerCard
      v-for="dweller in availableDwellers"
      :key="dweller.id"
      :dweller="dweller"
      :ability="ability"
      @activate="pickDweller($event)"
    />
    <p v-if="!availableDwellers.length" class="picker-empty">No available dwellers</p>
  </div>
</template>

<style scoped>
.dweller-picker {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.5rem;
  background: var(--color-surface-sunken);
  border: 1px solid var(--color-theme-glow);
  border-radius: 4px;
  max-height: 240px;
  overflow-y: auto;
}

.picker-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.picker-title {
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--color-theme-primary);
}

.picker-close {
  display: inline-flex;
  background: transparent;
  border: none;
  color: var(--color-gray-400);
  cursor: pointer;
  padding: 0.25rem;
  border-radius: 4px;
}

.picker-close:hover,
.picker-close:focus-visible {
  color: var(--color-theme-primary);
  outline: none;
}

.picker-empty {
  margin: 0;
  font-size: 0.75rem;
  color: var(--color-gray-400);
}
</style>
