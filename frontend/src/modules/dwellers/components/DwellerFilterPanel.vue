<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import {
  useDwellerStore,
  DWELLER_STATUSES,
  type DwellerStatus,
  type DwellerAgeGroup,
} from '@/modules/dwellers/stores/dweller'
import type { components } from '@/core/types/api.generated'
import { formatIdentityLabel, getRaceConfig, AGE_CONFIG_MAP, FACTION_CONFIG_MAP, GENDER_CONFIG_MAP } from '../models/dweller'
import { useFeatureFlagsStore } from '../stores/featureFlags'
import { useIdentityOptions } from '../composables/useIdentityOptions'
import DwellerFilterGroup from './DwellerFilterGroup.vue'

interface Props {
  showStatusFilter?: boolean
  showAgeFilter?: boolean
  showGenderFilter?: boolean
  showIdentityFilters?: boolean
  showActiveFilterSummary?: boolean
}

const {
  showStatusFilter = true,
  showAgeFilter = false,
  showGenderFilter = false,
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
  { value: 'all', label: 'All Races', icon: 'mdi:account-multiple' },
  ...races.value.map((race) => {
    const config = getRaceConfig(race)
    return { value: race, label: config.label, icon: config.icon }
  }),
])

/** Faction choices follow the chosen race, so only combinations the game allows are offered. */
const factionSelectOptions = computed(() => {
  const selectedRace = dwellerStore.filterRace
  const allowed =
    selectedRace === 'all'
      ? [...new Set(Object.values(factionsByRace.value).flat())].sort()
      : (factionsByRace.value[selectedRace] ?? [])

  return [
    { value: 'all', label: 'All Factions', icon: 'mdi:account-multiple' },
    ...allowed.map((faction) => {
      const config = FACTION_CONFIG_MAP[faction as components['schemas']['FactionEnum']]
      return { value: faction, label: config.label, icon: config.icon }
    }),
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
  { value: 'child', label: 'Child', icon: 'mdi:baby', accent: AGE_CONFIG_MAP.child.color },
  { value: 'teen', label: 'Teen', icon: 'mdi:human-child', accent: AGE_CONFIG_MAP.teen.color },
  { value: 'adult', label: 'Adult', icon: 'mdi:account', accent: AGE_CONFIG_MAP.adult.color },
  { value: 'elder', label: 'Elder', icon: 'mdi:account-cowboy-hat', accent: AGE_CONFIG_MAP.elder.color },
]

const genderOptions = [
  { value: 'all', label: 'All Genders', icon: 'mdi:account-multiple' },
  ...Object.entries(GENDER_CONFIG_MAP).map(([value, config]) => ({
    value,
    label: config.label,
    icon: config.icon,
    accent: config.color,
  })),
]

const currentFilterStatus = computed({
  get: () => dwellerStore.filterStatus,
  set: (value: DwellerStatus | 'all') => dwellerStore.setFilterStatus(value),
})

const currentFilterAgeGroup = computed({
  get: () => dwellerStore.filterAgeGroup,
  set: (value: DwellerAgeGroup) => dwellerStore.setFilterAgeGroup(value),
})

const currentFilterGender = computed({
  get: () => dwellerStore.filterGender,
  set: (value: string) => dwellerStore.setFilterGender(value),
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
    gender: showGenderFilter ? dwellerStore.filterGender : 'all',
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

/** Gender chips preview their own result set, following every filter except gender itself. */
const genderCounts = computed<Record<string, number> | undefined>(() => {
  if (!showGenderFilter || dwellerStore.allDwellers.length === 0) return undefined

  const { all, byGender } = dwellerStore.countByGender({
    status: showStatusFilter ? dwellerStore.filterStatus : 'all',
    ageGroup: showAgeFilter ? dwellerStore.filterAgeGroup : 'all',
    race: showIdentityFilters ? dwellerStore.filterRace : 'all',
    faction: showIdentityFilters ? dwellerStore.filterFaction : 'all',
  })

  return { all, ...byGender }
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
  if (showGenderFilter && dwellerStore.filterGender !== 'all') {
    labels.push(labelFor(genderOptions, dwellerStore.filterGender))
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
  dwellerStore.setFilterGender('all')
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

      <DwellerFilterGroup
        v-if="showGenderFilter"
        label="Filter by Gender"
        icon="mdi:gender-male-female"
        :options="genderOptions"
        :model-value="currentFilterGender"
        :counts="genderCounts"
        @update:model-value="currentFilterGender = $event"
      />

      <DwellerFilterGroup
        v-if="showIdentityFilters"
        label="Filter by Race"
        icon="mdi:account-star"
        :options="raceSelectOptions"
        :model-value="currentFilterRace"
        @update:model-value="currentFilterRace = $event"
      />

      <DwellerFilterGroup
        v-if="showIdentityFilters && featureFlags.factionMechanics"
        label="Filter by Faction"
        icon="mdi:shield-account"
        :options="factionSelectOptions"
        :model-value="currentFilterFaction"
        @update:model-value="currentFilterFaction = $event"
      />

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
    background-color 0.2s,
    border-color 0.2s,
    color 0.2s;
}

.filter-clear:hover {
  background: var(--color-surface-hover);
  border-color: var(--color-theme-primary);
}

.filter-clear:focus-visible {
  outline: 2px solid var(--color-theme-primary);
  outline-offset: 2px;
}

.filter-section-row {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}
</style>
