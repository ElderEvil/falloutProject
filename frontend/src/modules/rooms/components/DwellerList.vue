<script setup lang="ts">
import { computed, ref } from 'vue'
import { Icon } from '@iconify/vue'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import RoomDwellerCard from './RoomDwellerCard.vue'

interface Props {
  assignedDwellers: DwellerShort[]
  dwellerCapacity: number
  ability: string | null
  allowApprentice: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  dwellerClick: [dwellerId: string]
  assignDweller: [dwellerId: string]
  unassignDweller: [dwellerId: string]
}>()

const { filter: dwellerStore } = useDwellerStore()
type AssignmentMode = 'worker' | 'apprentice'

const assignmentMode = ref<AssignmentMode | null>(null)

const workers = computed(() => props.assignedDwellers.filter((dweller) => !dweller.apprentice_stat))
const hasFreeCapacity = computed(() => workers.value.length < props.dwellerCapacity)
const hasApprentice = computed(() => props.assignedDwellers.some((dweller) => dweller.apprentice_stat))
const canAssignApprentice = computed(() => props.allowApprentice && !hasApprentice.value)

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
  <div class="section dweller-section">
    <h3 class="section-title dweller-section-title">
      <Icon icon="mdi:account-group" class="h-5 w-5" />
      Staffing
    </h3>
    <div class="dwellers-list">
      <RoomDwellerCard
        v-for="dweller in assignedDwellers"
        :key="dweller.id"
        :dweller="dweller"
        :ability="ability"
        show-apprentice
        show-assignment-role
        show-unassign
        @activate="emit('dwellerClick', $event)"
        @unassign="emit('unassignDweller', $event)"
      />

      <div v-if="!assignmentMode" class="assignment-actions">
        <button
          type="button"
          class="assign-slot assign-worker"
          :disabled="!hasFreeCapacity"
          @click="assignmentMode = 'worker'"
        >
          <Icon icon="mdi:account-plus-outline" class="h-5 w-5" />
          <span>Assign Worker</span>
        </button>
        <button
          v-if="allowApprentice"
          type="button"
          class="assign-slot assign-apprentice"
          :disabled="!canAssignApprentice"
          @click="assignmentMode = 'apprentice'"
        >
          <Icon icon="mdi:school-outline" class="h-5 w-5" />
          <span>Assign Apprentice</span>
        </button>
      </div>

      <div v-if="assignmentMode" class="dweller-picker">
        <div class="picker-header">
          <span class="picker-title">{{ pickerTitle }}</span>
          <button type="button" class="picker-close" aria-label="Close picker" @click="assignmentMode = null">
            <Icon icon="mdi:close" class="h-4 w-4" />
          </button>
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
    </div>
  </div>
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
  font-size: 0.9375rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-theme-primary);
  margin: 0;
}

.section-title :deep(svg) {
  width: 1rem;
  height: 1rem;
}

.dweller-section {
  padding-top: 0.75rem;
  border-top: 1px solid var(--color-theme-glow);
}

.dweller-section-title {
  font-weight: 700;
}

.dwellers-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 0.5rem;
  max-height: 180px;
  overflow-y: auto;
}

.assignment-actions {
  display: grid;
  grid-column: 1 / -1;
  grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
  gap: 0.5rem;
}

.assign-slot {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  min-height: 64px;
  width: 100%;
  padding: 0.6rem 0.75rem;
  background: transparent;
  border: 1px dashed var(--color-theme-glow);
  color: var(--color-theme-primary);
  font: inherit;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.assign-apprentice {
  border-color: color-mix(in srgb, var(--color-warning) 70%, transparent);
  color: var(--color-warning);
}

.assign-slot:hover,
.assign-slot:focus-visible {
  border-color: var(--color-theme-primary);
  background: var(--color-surface-hover);
  outline: none;
}

.assign-apprentice:hover,
.assign-apprentice:focus-visible {
  border-color: var(--color-warning);
  background: color-mix(in srgb, var(--color-warning) 10%, transparent);
}

.assign-slot:disabled {
  cursor: not-allowed;
  opacity: 0.42;
}

.dweller-picker {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  grid-column: 1 / -1;
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
