<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { useDwellerStore, type DwellerStatus, type DwellerSortBy } from '@/stores/dweller'

interface Props {
  showStatusFilter?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  showStatusFilter: true
})

const dwellerStore = useDwellerStore()

const statusOptions = [
  { value: 'all', label: 'All', icon: 'mdi:account-multiple' },
  { value: 'idle', label: 'Idle', icon: 'mdi:coffee-outline' },
  { value: 'working', label: 'Working', icon: 'mdi:hammer-wrench' },
  { value: 'exploring', label: 'Exploring', icon: 'mdi:compass-outline' }
]

const sortOptions = [
  { value: 'name', label: 'Name', icon: 'mdi:alphabetical' },
  { value: 'level', label: 'Level', icon: 'mdi:star' },
  { value: 'strength', label: 'Strength', icon: 'mdi:arm-flex' },
  { value: 'perception', label: 'Perception', icon: 'mdi:eye' },
  { value: 'endurance', label: 'Endurance', icon: 'mdi:heart' },
  { value: 'charisma', label: 'Charisma', icon: 'mdi:account-heart' },
  { value: 'intelligence', label: 'Intelligence', icon: 'mdi:brain' },
  { value: 'agility', label: 'Agility', icon: 'mdi:run' },
  { value: 'luck', label: 'Luck', icon: 'mdi:clover' }
]

const currentFilterStatus = computed({
  get: () => dwellerStore.filterStatus,
  set: (value: DwellerStatus | 'all') => dwellerStore.setFilterStatus(value)
})

const currentSortBy = computed({
  get: () => dwellerStore.sortBy,
  set: (value: DwellerSortBy) => dwellerStore.setSortBy(value)
})

const currentSortDirection = computed({
  get: () => dwellerStore.sortDirection,
  set: (value: 'asc' | 'desc') => dwellerStore.setSortDirection(value)
})

const toggleSortDirection = () => {
  currentSortDirection.value = currentSortDirection.value === 'asc' ? 'desc' : 'asc'
}
</script>

<template>
  <div class="filter-panel">
    <div v-if="showStatusFilter" class="filter-section">
      <div class="section-header">
        <Icon icon="mdi:filter" />
        <span>Filter by Status</span>
      </div>
      <div class="button-group">
        <button
          v-for="option in statusOptions"
          :key="option.value"
          :class="{ active: currentFilterStatus === option.value }"
          @click="currentFilterStatus = option.value as DwellerStatus | 'all'"
          class="filter-button"
        >
          <Icon :icon="option.icon" />
          <span>{{ option.label }}</span>
        </button>
      </div>
    </div>

    <div class="filter-section">
      <div class="section-header">
        <Icon icon="mdi:sort" />
        <span>Sort By</span>
      </div>
      <div class="sort-controls">
        <select v-model="currentSortBy" class="sort-select">
          <option v-for="option in sortOptions" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
        <button @click="toggleSortDirection" class="sort-direction-button">
          <Icon
            :icon="currentSortDirection === 'asc' ? 'mdi:arrow-up' : 'mdi:arrow-down'"
            width="20"
            height="20"
          />
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.filter-panel {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  padding: 1rem;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.filter-section {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  font-weight: 600;
  color: #fbbf24;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.button-group {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.filter-button {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  color: #d1d5db;
  font-size: 0.875rem;
  cursor: pointer;
  transition: all 0.2s;
}

.filter-button:hover {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.2);
}

.filter-button.active {
  background: rgba(251, 191, 36, 0.2);
  border-color: #fbbf24;
  color: #fbbf24;
}

.sort-controls {
  display: flex;
  gap: 0.5rem;
}

.sort-select {
  flex: 1;
  padding: 0.5rem 1rem;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  color: #d1d5db;
  font-size: 0.875rem;
  cursor: pointer;
  transition: all 0.2s;
}

.sort-select:hover,
.sort-select:focus {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.2);
  outline: none;
}

.sort-direction-button {
  padding: 0.5rem;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  color: #d1d5db;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.sort-direction-button:hover {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.2);
}
</style>
