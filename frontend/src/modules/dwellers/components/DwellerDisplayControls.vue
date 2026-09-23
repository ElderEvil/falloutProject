<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { onClickOutside } from '@vueuse/core'
import { Icon } from '@iconify/vue'
import { useDwellerStore, type DwellerSortBy } from '@/modules/dwellers/stores/dweller'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/core/components/ui/select'
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

const onSortByChange = (value: unknown) => {
  sortByValue.value = String(value)
}

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
      <Select :model-value="sortByValue" @update:model-value="onSortByChange">
        <SelectTrigger
          size="sm"
          class="min-w-[8rem] border-theme-glow rounded-md px-3 py-2 text-[0.8125rem] opacity-[0.85] hover:opacity-100 hover:shadow-[0_0_8px_var(--color-theme-glow)]"
          aria-label="Sort dwellers"
        >
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem v-for="option in sortOptions" :key="option.value" :value="option.value">
            {{ option.label }}
          </SelectItem>
        </SelectContent>
      </Select>
      <button
        type="button"
        class="sort-direction-button"
        aria-label="Toggle sort direction"
        @click="toggleSortDirection"
      >
        <Icon :icon="sortDirection === 'asc' ? 'mdi:arrow-up' : 'mdi:arrow-down'" />
      </button>
    </div>

    <!-- Bespoke raw toggle buttons: custom scoped CSS + structural test selectors (docs/frontend/RAW_NATIVE_CONTROLS.md). -->
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
      Kept last in the island: the toolbar pins the island's left edge, so a trigger
      appended here grows it rightward and sort/view never shift when table mode opens.
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
        <div class="columns-head">
          <span class="preset-label">Quick presets</span>
          <button type="button" class="preset-reset" @click="dwellerStore.resetTableColumns()">
            Reset
          </button>
        </div>
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

/* Every button in the island shares this terminal control treatment; the rules below are
   only the deltas. The transition lists exactly what those deltas change — including
   font-weight, which the active view button steps from 500 to 600. */
.display-controls button {
  background: var(--color-surface-raised);
  border: 1px solid var(--color-theme-glow);
  border-radius: 6px;
  color: var(--color-theme-primary);
  font-family: inherit;
  cursor: pointer;
  transition:
    background-color 0.2s,
    border-color 0.2s,
    box-shadow 0.2s,
    opacity 0.2s,
    font-weight 0.2s;
}

.display-controls button:hover {
  background: var(--color-surface-hover);
  box-shadow: 0 0 8px var(--color-theme-glow);
}

.display-controls button:focus-visible {
  outline: 2px solid var(--color-theme-primary);
  outline-offset: 2px;
}

.sort-direction-button {
  padding: 0.5rem 0.75rem;
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

.columns-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

/* Qualified so it outweighs the shared rule and stays transparent. */
.display-controls .preset-reset {
  padding: 0.15rem 0.4rem;
  background: transparent;
  border-radius: 4px;
  font-size: 0.6875rem;
}

.preset-reset:hover {
  border-color: var(--color-theme-primary);
}

.view-toggle-btn {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.5rem 0.75rem;
  font-size: 0.8125rem;
  font-weight: 500;
  white-space: nowrap;
  opacity: 0.7;
}

.view-toggle-btn:hover {
  opacity: 0.9;
}

.view-toggle-btn.active {
  opacity: 1;
  background: var(--color-surface-hover);
  border-color: var(--color-theme-primary);
  box-shadow: 0 0 12px var(--color-theme-primary);
  font-weight: 600;
}

/* The sort arrow defaults to 16px/20px; the chips use 1em. */
.sort-direction-button :deep(svg) {
  width: 1em;
  height: 1em;
}
</style>
