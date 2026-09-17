<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { onClickOutside } from '@vueuse/core'
import { Icon } from '@iconify/vue'
import { useDwellerStore, type DwellerSortBy } from '@/modules/dwellers/stores/dweller'
import USelect from '@/core/components/ui/USelect.vue'
import { DWELLER_TABLE_COLUMNS, DWELLER_TABLE_PRESETS } from '../models/dwellerTable'

interface Props {
  showSort?: boolean
  showView?: boolean
}

const { showSort = true, showView = false } = defineProps<Props>()

const { filter: dwellerStore } = useDwellerStore()

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

/** The dropdown speaks plain strings; the store keeps the narrower sort union. */
const sortByValue = computed({
  get: () => dwellerStore.sortBy as string,
  set: (value: string) => dwellerStore.setSortBy(value as DwellerSortBy),
})

const sortDirection = computed({
  get: () => dwellerStore.sortDirection,
  set: (value: 'asc' | 'desc') => dwellerStore.setSortDirection(value),
})

const toggleSortDirection = () => {
  sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
}

const columnsMenuOpen = ref(false)
const columnsTrigger = ref<HTMLElement | null>(null)

onClickOutside(columnsTrigger, () => {
  columnsMenuOpen.value = false
})

// The menu belongs to table view, so leaving it must not leave the menu open.
watch(
  () => dwellerStore.viewMode,
  (mode) => {
    if (mode !== 'table') columnsMenuOpen.value = false
  }
)

const visibleColumnCount = computed(() => dwellerStore.tableColumns.length)

function applyPreset(presetId: string) {
  dwellerStore.applyTablePreset(presetId)
  columnsMenuOpen.value = false
}
</script>

<template>
  <div class="display-controls">
    <div v-if="showSort" class="display-group">
      <USelect v-model="sortByValue" :options="sortOptions" size="sm" ariaLabel="Sort dwellers" />
      <button
        type="button"
        class="sort-direction-button"
        aria-label="Toggle sort direction"
        @click="toggleSortDirection"
      >
        <Icon :icon="sortDirection === 'asc' ? 'mdi:arrow-up' : 'mdi:arrow-down'" />
      </button>
    </div>

    <div v-if="showView" class="view-toggle-controls">
      <button
        type="button"
        :class="['view-toggle-btn', dwellerStore.viewMode === 'list' ? 'active' : '']"
        @click="dwellerStore.setViewMode('list')"
      >
        <Icon icon="mdi:view-list" width="18" height="18" />
        <span>List</span>
      </button>
      <button
        type="button"
        :class="['view-toggle-btn', dwellerStore.viewMode === 'grid' ? 'active' : '']"
        @click="dwellerStore.setViewMode('grid')"
      >
        <Icon icon="mdi:view-grid" width="18" height="18" />
        <span>Grid</span>
      </button>
      <button
        type="button"
        :class="['view-toggle-btn', dwellerStore.viewMode === 'table' ? 'active' : '']"
        @click="dwellerStore.setViewMode('table')"
      >
        <Icon icon="mdi:table" width="18" height="18" />
        <span>Table</span>
      </button>
    </div>

    <!--
      Visual order is forced ahead of sort/view via `order: -1` so that when this
      appears the island grows leftward and the controls keep their spread from the
      right edge instead of jumping.
    -->
    <div
      v-if="showView && dwellerStore.viewMode === 'table'"
      ref="columnsTrigger"
      class="columns-trigger"
      @keydown.escape="columnsMenuOpen = false"
    >
      <button
        type="button"
        class="view-toggle-btn"
        :class="{ active: columnsMenuOpen }"
        aria-haspopup="true"
        :aria-expanded="columnsMenuOpen"
        @click="columnsMenuOpen = !columnsMenuOpen"
      >
        <Icon icon="mdi:table-column" width="18" height="18" />
        <span>Columns {{ visibleColumnCount }}</span>
        <Icon
          :icon="columnsMenuOpen ? 'mdi:chevron-up' : 'mdi:chevron-down'"
          width="16"
          height="16"
        />
      </button>

      <div v-if="columnsMenuOpen" class="columns-menu">
        <span class="preset-label">Quick presets</span>
        <div class="view-toggle-controls">
          <button
            v-for="preset in DWELLER_TABLE_PRESETS"
            :key="preset.id"
            type="button"
            class="view-toggle-btn"
            @click="applyPreset(preset.id)"
          >
            <Icon :icon="preset.icon" width="18" height="18" />
            <span>{{ preset.label }}</span>
          </button>
        </div>
        <div class="view-toggle-controls">
          <button
            v-for="column in DWELLER_TABLE_COLUMNS"
            :key="column.id"
            type="button"
            :class="[
              'view-toggle-btn',
              dwellerStore.tableColumns.includes(column.id) ? 'active' : '',
            ]"
            :aria-pressed="dwellerStore.tableColumns.includes(column.id)"
            @click="dwellerStore.toggleTableColumn(column.id)"
          >
            <Icon :icon="column.icon" width="18" height="18" />
            <span>{{ column.label }}</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.display-controls {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  padding: 0.375rem 0.5rem;
  background: var(--color-surface-sunken);
  border: 1px solid rgb(from var(--color-theme-primary) r g b / 0.2);
  border-radius: 8px;
}

.display-group {
  display: flex;
  align-items: center;
  gap: 0.375rem;
}

.display-group :deep(.select-wrapper) {
  min-width: 8rem;
}

.sort-direction-button {
  padding: 0.5rem 0.75rem;
  background: var(--color-surface-raised);
  border: 1px solid var(--color-theme-glow);
  border-radius: 6px;
  color: var(--color-theme-primary);
  cursor: pointer;
  transition:
    background-color 0.2s,
    border-color 0.2s,
    box-shadow 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.sort-direction-button:hover {
  background: var(--color-surface-hover);
  box-shadow: 0 0 8px var(--color-theme-glow);
}

.sort-direction-button:focus-visible {
  outline: 2px solid var(--color-theme-primary);
  outline-offset: 2px;
}

.view-toggle-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem;
}

.columns-trigger {
  order: -1;
  position: relative;
}

.columns-menu {
  position: absolute;
  z-index: 10;
  top: 100%;
  left: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  width: max-content;
  max-width: 24rem;
  margin-top: 0.25rem;
  padding: 0.5rem;
  background: var(--color-surface-raised);
  border: 1px solid color-mix(in srgb, var(--color-theme-primary) 45%, transparent);
  border-radius: var(--border-radius-base);
  box-shadow: 0 8px 20px var(--color-theme-glow);
}

.preset-label {
  color: var(--color-theme-primary);
  font-size: 0.6875rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  opacity: 0.6;
}

.view-toggle-btn {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.5rem 0.75rem;
  background: var(--color-surface-raised);
  border: 1px solid var(--color-theme-glow);
  border-radius: 6px;
  color: var(--color-theme-primary);
  font-size: 0.8125rem;
  font-weight: 500;
  cursor: pointer;
  transition:
    opacity 0.2s,
    background-color 0.2s,
    border-color 0.2s,
    box-shadow 0.2s;
  white-space: nowrap;
  opacity: 0.7;
}

.view-toggle-btn:hover {
  opacity: 0.9;
  background: var(--color-surface-hover);
  box-shadow: 0 0 8px var(--color-theme-glow);
}

.view-toggle-btn:focus-visible {
  outline: 2px solid var(--color-theme-primary);
  outline-offset: 2px;
}

.view-toggle-btn.active {
  opacity: 1;
  background: var(--color-surface-hover);
  border-color: var(--color-theme-primary);
  box-shadow: 0 0 12px var(--color-theme-primary);
  font-weight: 600;
}

/* The USelect chevron and the sort arrow default to 16px/20px; the chips use 1em. */
.sort-direction-button :deep(svg) {
  width: 1em;
  height: 1em;
}

/* Kept identical to the filter panel's identity selects so the toolbar reads as one set. */
.display-group :deep(.select-trigger) {
  padding: 0.5rem 0.75rem;
  border-color: var(--color-theme-glow);
  border-radius: 6px;
  font-size: 0.8125rem;
  opacity: 0.85;
}

.display-group :deep(.select-trigger svg) {
  width: 1em;
  height: 1em;
}

.display-group :deep(.select-trigger:hover) {
  opacity: 1;
  box-shadow: 0 0 8px var(--color-theme-glow);
}
</style>
