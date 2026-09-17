<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { Icon } from '@iconify/vue'
import {
  useDwellerStore,
  DWELLER_STATUSES,
  type DwellerStatus,
  type DwellerAgeGroup,
} from '@/modules/dwellers/stores/dweller'
import { formatIdentityLabel } from '../models/dweller'
import { useFeatureFlagsStore } from '../stores/featureFlags'
import { useIdentityOptions } from '../composables/useIdentityOptions'
import USelect from '@/core/components/ui/USelect.vue'
import DwellerFilterGroup from './DwellerFilterGroup.vue'

interface Props {
  showStatusFilter?: boolean
  showAgeFilter?: boolean
  showIdentityFilters?: boolean
  showActiveFilterSummary?: boolean
}

const {
  showStatusFilter = true,
  showAgeFilter = false,
  showIdentityFilters = false,
  showActiveFilterSummary = false,
} = defineProps<Props>()

const { filter: dwellerStore } = useDwellerStore()
const featureFlags = useFeatureFlagsStore()
const {
  races,
  factionsByRace,
  loaded: identityOptionsLoaded,
  load: loadIdentityOptions,
} = useIdentityOptions()

onMounted(async () => {
  await featureFlags.fetchFlags()
  if (!showIdentityFilters) return

  await loadIdentityOptions()
  if (!identityOptionsLoaded.value) return

  // A persisted selection can outlive the options it came from, and the watcher below
  // only reacts to a race *change* — so validate what was restored here.
  if (dwellerStore.filterRace !== 'all' && !races.value.includes(dwellerStore.filterRace)) {
    dwellerStore.setFilterRace('all')
  }
  dropStrandedFaction()
})

const raceSelectOptions = computed(() => [
  { value: 'all', label: 'All Races' },
  ...races.value.map((race) => ({ value: race, label: formatIdentityLabel(race) })),
])

/** Faction choices follow the chosen race, so only combinations the game allows are offered. */
const factionSelectOptions = computed(() => {
  const selectedRace = dwellerStore.filterRace
  const allowed =
    selectedRace === 'all'
      ? [...new Set(Object.values(factionsByRace.value).flat())].sort()
      : (factionsByRace.value[selectedRace] ?? [])

  return [
    { value: 'all', label: 'All Factions' },
    ...allowed.map((faction) => ({ value: faction, label: formatIdentityLabel(faction) })),
  ]
})

/** A faction only makes sense while the chosen race can hold it. */
function dropStrandedFaction() {
  if (!identityOptionsLoaded.value || dwellerStore.filterFaction === 'all') return
  const allowed = factionSelectOptions.value.map((option) => option.value)
  if (!allowed.includes(dwellerStore.filterFaction)) dwellerStore.setFilterFaction('all')
}

// Switching race can strand a faction the new race cannot hold.
watch(() => dwellerStore.filterRace, dropStrandedFaction)

const statusOptions = [
  { value: 'all', label: 'All', icon: 'mdi:account-multiple' },
  { value: 'idle', label: 'Idle', icon: 'mdi:coffee-outline' },
  { value: 'resting', label: 'Socializing', icon: 'mdi:heart-outline' },
  { value: 'working', label: 'Working', icon: 'mdi:hammer-wrench' },
  { value: 'training', label: 'Training', icon: 'mdi:dumbbell' },
  { value: 'exploring', label: 'Exploring', icon: 'mdi:compass-outline' },
  { value: 'questing', label: 'Questing', icon: 'mdi:sword-cross' },
  { value: 'fighting', label: 'Fighting', icon: 'mdi:boxing-glove' },
  { value: 'dead', label: 'Dead', icon: 'mdi:skull' },
]

const ageGroupOptions = [
  { value: 'all', label: 'All Ages', icon: 'mdi:account-multiple' },
  { value: 'child', label: 'Child', icon: 'mdi:baby' },
  { value: 'teen', label: 'Teen', icon: 'mdi:human-child' },
  { value: 'adult', label: 'Adult', icon: 'mdi:account' },
]

const currentFilterStatus = computed({
  get: () => dwellerStore.filterStatus,
  set: (value: DwellerStatus | 'all') => dwellerStore.setFilterStatus(value),
})

const currentFilterAgeGroup = computed({
  get: () => dwellerStore.filterAgeGroup,
  set: (value: DwellerAgeGroup) => dwellerStore.setFilterAgeGroup(value),
})

const currentFilterRace = computed({
  get: () => dwellerStore.filterRace,
  set: (value: string) => dwellerStore.setFilterRace(value),
})

const currentFilterFaction = computed({
  get: () => dwellerStore.filterFaction,
  set: (value: string) => dwellerStore.setFilterFaction(value),
})

/** Chips preview their own result set, so counts follow only the filters on screen. */
const statusCounts = computed<Record<string, number> | undefined>(() => {
  if (!showStatusFilter || dwellerStore.allDwellers.length === 0) return undefined

  const { all, byStatus } = dwellerStore.countByStatus({
    ageGroup: showAgeFilter ? dwellerStore.filterAgeGroup : 'all',
    race: showIdentityFilters ? dwellerStore.filterRace : 'all',
    faction: showIdentityFilters ? dwellerStore.filterFaction : 'all',
  })

  const counts: Record<string, number> = { all }
  for (const status of DWELLER_STATUSES) {
    // Dead is served by its own endpoint, so a count here would not match its panel.
    if (status === 'dead') continue
    counts[status] = byStatus[status]
  }
  return counts
})

function labelFor(options: readonly { value: string; label: string }[], value: string): string {
  return options.find((option) => option.value === value)?.label ?? value
}

/** Only facets whose controls are on screen: a hidden control must not be advertised. */
const activeFilterLabels = computed(() => {
  const labels: string[] = []
  if (showStatusFilter && dwellerStore.filterStatus !== 'all') {
    labels.push(labelFor(statusOptions, dwellerStore.filterStatus))
  }
  if (showAgeFilter && dwellerStore.filterAgeGroup !== 'all') {
    labels.push(labelFor(ageGroupOptions, dwellerStore.filterAgeGroup))
  }
  if (showIdentityFilters && dwellerStore.filterRace !== 'all') {
    labels.push(formatIdentityLabel(dwellerStore.filterRace))
  }
  if (
    showIdentityFilters &&
    featureFlags.factionMechanics &&
    dwellerStore.filterFaction !== 'all'
  ) {
    labels.push(formatIdentityLabel(dwellerStore.filterFaction))
  }
  return labels
})

const hasActiveFilters = computed(() => activeFilterLabels.value.length > 0)

function clearFilters(): void {
  dwellerStore.setFilterStatus('all')
  dwellerStore.setFilterAgeGroup('all')
  dwellerStore.setFilterRace('all')
  dwellerStore.setFilterFaction('all')
}
</script>

<template>
  <div class="filter-panel">
    <div v-if="showActiveFilterSummary && hasActiveFilters" class="filter-summary">
      <span class="filter-summary-labels">{{ activeFilterLabels.join(' · ') }}</span>
      <button type="button" class="filter-clear" @click="clearFilters">Clear all</button>
    </div>

    <DwellerFilterGroup
      v-if="showStatusFilter"
      label="Filter by Status"
      icon="mdi:filter"
      :options="statusOptions"
      :model-value="currentFilterStatus"
      :counts="statusCounts"
      @update:model-value="currentFilterStatus = $event as DwellerStatus | 'all'"
    />

    <div class="filter-section-row">
      <DwellerFilterGroup
        v-if="showAgeFilter"
        label="Filter by Age"
        icon="mdi:account-group"
        :options="ageGroupOptions"
        :model-value="currentFilterAgeGroup"
        @update:model-value="currentFilterAgeGroup = $event as DwellerAgeGroup"
      />

      <div v-if="showIdentityFilters" class="filter-section">
        <div class="section-header">
          <Icon icon="mdi:account-star" />
          <span>Filter by Identity</span>
        </div>
        <div class="identity-controls">
          <USelect
            v-model="currentFilterRace"
            :options="raceSelectOptions"
            size="sm"
            placeholder="All Races"
          />
          <USelect
            v-if="featureFlags.factionMechanics"
            v-model="currentFilterFaction"
            :options="factionSelectOptions"
            size="sm"
            placeholder="All Factions"
          />
        </div>
      </div>

      <slot v-if="$slots['additional-filters']" name="additional-filters"></slot>
    </div>
  </div>
</template>

<style scoped>
.filter-panel {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 0.75rem;
  background: var(--color-surface-sunken);
  border-radius: 8px;
  border: 1px solid rgb(from var(--color-theme-primary) r g b / 0.2);
}

.filter-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  padding: 0.375rem 0.5rem;
  background: color-mix(in srgb, var(--color-theme-primary) 8%, transparent);
  border: 1px solid rgb(from var(--color-theme-primary) r g b / 0.2);
  border-radius: 6px;
}

.filter-summary-labels {
  min-width: 0;
  overflow: hidden;
  color: var(--color-theme-primary);
  font-size: 0.75rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.filter-clear {
  flex-shrink: 0;
  padding: 0.25rem 0.5rem;
  background: transparent;
  border: 1px solid var(--color-theme-glow);
  border-radius: 4px;
  color: var(--color-theme-primary);
  font-family: inherit;
  font-size: 0.75rem;
  cursor: pointer;
  transition:
    background 0.2s,
    border-color 0.2s,
    outline 0.2s;
}

.filter-clear:hover {
  background: var(--color-surface-hover);
  border-color: var(--color-theme-primary);
}

.filter-clear:focus-visible {
  outline: 2px solid var(--color-theme-primary);
  outline-offset: 2px;
}

.filter-section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--color-theme-primary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  text-shadow: 0 0 4px var(--color-theme-glow);
}

.filter-section-row {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.identity-controls {
  display: flex;
  gap: 0.5rem;
}

/* Hug the widest race label ("Super Mutant") rather than stretching a lone select across the row. */
.identity-controls :deep(.select-wrapper) {
  flex: 0 0 auto;
  min-width: 8.5rem;
}

/* Match the status/age chips, keeping the inherited line-height so the heights agree. */
.identity-controls :deep(.select-trigger) {
  padding: 0.5rem 0.75rem;
  border-color: var(--color-theme-glow);
  border-radius: 6px;
  font-size: 0.8125rem;
  opacity: 0.85;
}

/* The USelect chevron defaults to 16px/20px; the chips use 1em. */
.identity-controls :deep(.select-trigger svg) {
  width: 1em;
  height: 1em;
}

.identity-controls :deep(.select-trigger:hover) {
  opacity: 1;
  box-shadow: 0 0 8px var(--color-theme-glow);
}

.flex-grow {
  flex-grow: 1;
}

.bulk-action-controls {
  display: flex;
  gap: 0.5rem;
}
</style>
