<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import {
  useDwellerStore,
  type DwellerStatus,
  type DwellerSortBy,
  type DwellerAgeGroup,
} from '@/stores/dweller'

interface Props {
  showStatusFilter?: boolean
  showAgeFilter?: boolean
  showViewToggle?: boolean
  showBulkActions?: boolean
  vaultId?: string
}

const props = withDefaults(defineProps<Props>(), {
  showStatusFilter: true,
  showAgeFilter: false,
  showViewToggle: false,
  showBulkActions: false,
  vaultId: '',
})

defineEmits<{
  unassignAll: []
  autoAssignAll: []
}>()

const dwellerStore = useDwellerStore()

const statusOptions = [
  { value: 'all', label: 'All', icon: 'mdi:account-multiple' },
  { value: 'idle', label: 'Idle', icon: 'mdi:coffee-outline' },
  { value: 'working', label: 'Working', icon: 'mdi:hammer-wrench' },
  { value: 'training', label: 'Training', icon: 'mdi:dumbbell' },
  { value: 'exploring', label: 'Exploring', icon: 'mdi:compass-outline' },
  { value: 'questing', label: 'Questing', icon: 'mdi:sword-cross' },
  { value: 'dead', label: 'Dead', icon: 'mdi:skull' },
]

const ageGroupOptions = [
  { value: 'all', label: 'All Ages', icon: 'mdi:account-multiple' },
  { value: 'child', label: 'Child', icon: 'mdi:baby' },
  { value: 'teen', label: 'Teen', icon: 'mdi:human-child' },
  { value: 'adult', label: 'Adult', icon: 'mdi:account' },
]

const sortOptions = [
  { value: 'name', label: 'Name', icon: 'mdi:alphabetical' },
  { value: 'level', label: 'Level', icon: 'mdi:star' },
  { value: 'happiness', label: 'Happiness', icon: 'mdi:emoticon-happy' },
  { value: 'strength', label: 'Strength', icon: 'mdi:arm-flex' },
  { value: 'perception', label: 'Perception', icon: 'mdi:eye' },
  { value: 'endurance', label: 'Endurance', icon: 'mdi:heart' },
  { value: 'charisma', label: 'Charisma', icon: 'mdi:account-heart' },
  { value: 'intelligence', label: 'Intelligence', icon: 'mdi:brain' },
  { value: 'agility', label: 'Agility', icon: 'mdi:run' },
  { value: 'luck', label: 'Luck', icon: 'mdi:clover' },
]

const currentFilterStatus = computed({
  get: () => dwellerStore.filterStatus,
  set: (value: DwellerStatus | 'all') => dwellerStore.setFilterStatus(value),
})

const currentFilterAgeGroup = computed({
  get: () => dwellerStore.filterAgeGroup,
  set: (value: DwellerAgeGroup) => dwellerStore.setFilterAgeGroup(value),
})

const currentSortBy = computed({
  get: () => dwellerStore.sortBy,
  set: (value: DwellerSortBy) => dwellerStore.setSortBy(value),
})

const currentSortDirection = computed({
  get: () => dwellerStore.sortDirection,
  set: (value: 'asc' | 'desc') => dwellerStore.setSortDirection(value),
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

    <div v-if="showAgeFilter" class="filter-section">
      <div class="section-header">
        <Icon icon="mdi:account-group" />
        <span>Filter by Age</span>
      </div>
      <div class="button-group">
        <button
          v-for="option in ageGroupOptions"
          :key="option.value"
          :class="{ active: currentFilterAgeGroup === option.value }"
          @click="currentFilterAgeGroup = option.value as DwellerAgeGroup"
          class="filter-button"
        >
          <Icon :icon="option.icon" />
          <span>{{ option.label }}</span>
        </button>
      </div>
    </div>

    <div class="filter-section-row">
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

      <!-- Spacer to push bulk actions and view toggle to the right -->
      <div v-if="showBulkActions" class="flex-grow"></div>

      <!-- Bulk Actions (inline with sort/view) -->
      <div v-if="showBulkActions" class="filter-section">
        <div class="section-header">
          <Icon icon="mdi:account-multiple-check" />
          <span>Bulk Actions</span>
        </div>
        <div class="bulk-action-controls">
          <slot name="bulk-actions"></slot>
        </div>
      </div>

      <div v-if="showViewToggle" class="filter-section">
        <div class="section-header">
          <Icon icon="mdi:view-comfy" />
          <span>View</span>
        </div>
        <div class="view-toggle-controls">
          <button
            :class="['view-toggle-btn', dwellerStore.viewMode === 'list' ? 'active' : '']"
            @click="dwellerStore.setViewMode('list')"
          >
            <Icon icon="mdi:view-list" width="18" height="18" />
            <span>List</span>
          </button>
          <button
            :class="['view-toggle-btn', dwellerStore.viewMode === 'grid' ? 'active' : '']"
            @click="dwellerStore.setViewMode('grid')"
          >
            <Icon icon="mdi:view-grid" width="18" height="18" />
            <span>Grid</span>
          </button>
        </div>
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
  color: var(--color-theme-primary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  text-shadow: 0 0 4px var(--color-theme-glow);
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
  background: rgba(31, 41, 55, 0.4);
  border: 1px solid var(--color-theme-glow);
  border-radius: 6px;
  color: var(--color-theme-primary);
  font-size: 0.875rem;
  cursor: pointer;
  transition: all 0.2s;
  opacity: 0.6;
}

.filter-button:hover {
  opacity: 0.8;
  background: rgba(31, 41, 55, 0.6);
  box-shadow: 0 0 8px var(--color-theme-glow);
}

.filter-button.active {
  opacity: 1;
  background: rgba(31, 41, 55, 0.9);
  border-color: var(--color-theme-primary);
  box-shadow: 0 0 12px var(--color-theme-primary);
  font-weight: 600;
}

.sort-controls {
  display: flex;
  gap: 0.5rem;
}

.sort-select {
  flex: 1;
  padding: 0.5rem 1rem;
  background: rgba(31, 41, 55, 0.6);
  border: 1px solid var(--color-theme-glow);
  border-radius: 6px;
  color: var(--color-theme-primary);
  font-size: 0.875rem;
  cursor: pointer;
  transition: all 0.2s;
}

.sort-select:hover,
.sort-select:focus {
  background: rgba(31, 41, 55, 0.8);
  box-shadow: 0 0 8px var(--color-theme-glow);
  outline: none;
}

.sort-direction-button {
  padding: 0.5rem;
  background: rgba(31, 41, 55, 0.6);
  border: 1px solid var(--color-theme-glow);
  border-radius: 6px;
  color: var(--color-theme-primary);
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.sort-direction-button:hover {
  background: rgba(31, 41, 55, 0.8);
  box-shadow: 0 0 8px var(--color-theme-glow);
}

.filter-section-row {
  display: flex;
  gap: 1.5rem;
  flex-wrap: wrap;
}

.view-toggle-controls {
  display: flex;
  gap: 0.5rem;
}

.view-toggle-btn {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.5rem 0.875rem;
  background: rgba(31, 41, 55, 0.6);
  border: 1px solid var(--color-theme-glow);
  border-radius: 6px;
  color: var(--color-theme-primary);
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
  opacity: 0.7;
}

.view-toggle-btn:hover {
  opacity: 0.9;
  background: rgba(31, 41, 55, 0.8);
  box-shadow: 0 0 8px var(--color-theme-glow);
}

.view-toggle-btn.active {
  opacity: 1;
  background: rgba(31, 41, 55, 0.9);
  border-color: var(--color-theme-primary);
  box-shadow: 0 0 12px var(--color-theme-primary);
  font-weight: 600;
}

.flex-grow {
  flex-grow: 1;
}

.bulk-action-controls {
  display: flex;
  gap: 0.5rem;
}
</style>
