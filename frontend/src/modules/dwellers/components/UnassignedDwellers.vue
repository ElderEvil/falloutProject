<script setup lang="ts">
import { computed, ref } from 'vue'
import { useDwellerStore } from '../stores/dweller'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useToast } from '@/core/composables/useToast'
import { Icon } from '@iconify/vue'
import type { components } from '@/core/types/api.generated'
import type { DwellerShort } from '../models/dweller'
import DwellerAgeBadge from './DwellerAgeBadge.vue'
import DwellerGenderBadge from './DwellerGenderBadge.vue'
import DwellerRarityBadge from './DwellerRarityBadge.vue'
import DwellerFilterPanel from './DwellerFilterPanel.vue'
import DwellerPortrait from './DwellerPortrait.vue'

type RarityFilter = 'all' | components['schemas']['RarityEnum']

const { filter: dwellerStore, management: dwellerManagementStore } = useDwellerStore()
const authStore = useAuthStore()
const toast = useToast()

// Filter preferences are now automatically loaded via useLocalStorage in the store

// Rarity is specific to this compact assignment panel; age and sorting use
// the shared preferences from the Dwellers view.
const filterRarity = ref<RarityFilter>('all')

const RARITY_FILTERS: { value: RarityFilter; label: string; icon: string }[] = [
  { value: 'all', label: 'All', icon: 'mdi:star-circle-outline' },
  { value: 'common', label: 'Common', icon: 'mdi:star-outline' },
  { value: 'rare', label: 'Rare', icon: 'mdi:star' },
  { value: 'legendary', label: 'Legendary', icon: 'mdi:star-four-points' },
]

const RARITY_ACCENT: Record<string, string> = {
  common: 'var(--color-rarity-common)',
  rare: 'var(--color-rarity-rare)',
  legendary: 'var(--color-rarity-legendary)',
}

const rarityColor = (rarity?: string | null): string =>
  RARITY_ACCENT[String(rarity ?? '').toLowerCase()] ?? 'var(--color-rarity-common)'

// Must not have a room assignment, and must not be out of the vault
// (exploring or on a quest) or dead.
const isUnassignable = (dweller: DwellerShort): boolean =>
  !dweller.room_id && !['dead', 'questing', 'exploring'].includes(dweller.status)

const hasAnyUnassigned = computed(() => dwellerStore.dwellersWithStatus.some(isUnassignable))

// Use unfiltered dwellers from store, but only show unassigned ones
// We manually apply sorting here to respect the sort preference without being affected by the global status filter
const unassignedDwellers = computed(() => {
  const filtered = dwellerStore.dwellersWithStatus.filter(
    (dweller) =>
      isUnassignable(dweller) &&
      (dwellerStore.filterAgeGroup === 'all' || dweller.age_group === dwellerStore.filterAgeGroup) &&
      (filterRarity.value === 'all' || dweller.rarity === filterRarity.value)
  )

  // 2. Sort based on store preferences (shared with filter panel)
  return filtered.sort((a, b) => {
    let comparison = 0
    const sortBy = dwellerStore.sortBy

    if (sortBy === 'name') {
      const nameA = `${a.first_name} ${a.last_name}`.toLowerCase()
      const nameB = `${b.first_name} ${b.last_name}`.toLowerCase()
      comparison = nameA.localeCompare(nameB)
    } else if (sortBy === 'level' || sortBy === 'happiness') {
      comparison = (a[sortBy] || 0) - (b[sortBy] || 0)
    } else {
      // SPECIAL stats
      comparison = (a[sortBy] || 0) - (b[sortBy] || 0)
    }

    return dwellerStore.sortDirection === 'asc' ? comparison : -comparison
  })
})

const isDraggingOver = ref(false)

const emit = defineEmits<{
  dragStart: [dweller: DwellerShort]
  dragEnd: []
}>()

const handleDragStart = (event: DragEvent, dweller: DwellerShort) => {
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData(
      'application/json',
      JSON.stringify({
        dwellerId: dweller.id,
        firstName: dweller.first_name,
        lastName: dweller.last_name,
      })
    )
  }
  emit('dragStart', dweller)
}

const handleDragEnd = () => {
  emit('dragEnd')
}

const handleDropZoneDragOver = (event: DragEvent) => {
  event.preventDefault()
  event.dataTransfer!.dropEffect = 'move'
  isDraggingOver.value = true
}

const handleDropZoneDragLeave = () => {
  isDraggingOver.value = false
}

const handleDropZoneDrop = async (event: DragEvent) => {
  event.preventDefault()
  isDraggingOver.value = false

  try {
    const data = JSON.parse(event.dataTransfer!.getData('application/json'))
    const { dwellerId, firstName, lastName, currentRoomId } = data

    // Only unassign if dweller is currently in a room
    if (!currentRoomId) {
      return
    }

    await dwellerManagementStore.unassignDwellerFromRoom(dwellerId, authStore.token as string)

    toast.success(`${firstName} ${lastName} unassigned from room`)
  } catch {
    toast.error('Failed to unassign dweller')
  }
}

</script>

<template>
  <div class="unassigned-dwellers-panel">
    <div class="panel-header">
      <div class="header-row">
        <div>
          <h3 class="panel-title">
            <Icon icon="mdi:account-multiple" class="inline h-5 w-5" />
            Unassigned Dwellers
            <span class="count-badge">{{ unassignedDwellers.length }}</span>
          </h3>
          <p class="panel-subtitle">Drag dwellers here to unassign them from rooms</p>
        </div>

        <!-- Sort controls inline with header -->
        <DwellerFilterPanel :show-status-filter="false" :show-age-filter="true">
          <template #additional-filters>
            <div class="chip-group" role="group" aria-label="Filter by rarity">
              <div class="chip-group-label">
                <Icon icon="mdi:star-four-points" class="chip-group-icon" />
                <span>Rarity</span>
              </div>
              <button
                v-for="option in RARITY_FILTERS"
                :key="option.value"
                class="chip"
                :class="{ active: filterRarity === option.value }"
                :style="option.value === 'all' ? undefined : { '--chip-accent': rarityColor(option.value) }"
                :aria-pressed="filterRarity === option.value"
                @click="filterRarity = option.value"
              >
                <Icon :icon="option.icon" class="chip-icon" />
                {{ option.label }}
              </button>
            </div>
          </template>
        </DwellerFilterPanel>
      </div>
    </div>

    <div
      v-if="unassignedDwellers.length === 0"
      class="empty-state"
      :class="{ 'drop-zone-active': isDraggingOver }"
      @dragover="handleDropZoneDragOver"
      @dragleave="handleDropZoneDragLeave"
      @drop="handleDropZoneDrop"
    >
      <template v-if="isDraggingOver">
        <Icon
          icon="mdi:arrow-down-bold"
          class="h-12 w-12 animate-bounce"
          :style="{ color: 'var(--color-theme-primary)' }"
        />
        <p class="drop-message">Drop to unassign</p>
      </template>
      <template v-else-if="hasAnyUnassigned">
        <Icon
          icon="mdi:filter-off-outline"
          class="h-12 w-12"
          :style="{ color: 'var(--color-theme-primary)' }"
        />
        <p>No dwellers match the filters</p>
      </template>
      <template v-else>
        <Icon
          icon="mdi:check-circle"
          class="h-12 w-12"
          :style="{ color: 'var(--color-theme-primary)' }"
        />
        <p>All dwellers are assigned!</p>
      </template>
    </div>

    <div
      v-else
      class="dweller-grid-container"
      @dragover="handleDropZoneDragOver"
      @dragleave="handleDropZoneDragLeave"
      @drop="handleDropZoneDrop"
    >
      <div v-if="isDraggingOver" class="drop-overlay">
        <Icon icon="mdi:arrow-down-bold" class="h-12 w-12 animate-bounce" />
        <p>Drop to unassign</p>
      </div>

      <div class="dweller-grid">
        <div
          v-for="dweller in unassignedDwellers"
          :key="dweller.id"
          class="dweller-card"
          draggable="true"
          @dragstart="handleDragStart($event, dweller)"
          @dragend="handleDragEnd"
        >
          <div class="dweller-top">
            <div class="dweller-avatar" :style="{ '--rarity-ring': rarityColor(dweller.rarity) }">
              <DwellerPortrait
                :thumbnail-url="dweller.thumbnail_url"
                :alt="`${dweller.first_name} ${dweller.last_name}`"
                image-class="avatar-image"
                fallback-class="h-14 w-14 text-theme-primary/60"
              />
            </div>

            <div class="dweller-heading">
              <p class="dweller-name">{{ dweller.first_name }} {{ dweller.last_name }}</p>
              <div class="dweller-meta">
                <span class="dweller-level">Lv {{ dweller.level }}</span>
                <DwellerAgeBadge :age-group="dweller.age_group" size="sm" />
                <DwellerGenderBadge :gender="dweller.gender" size="sm" />
                <DwellerRarityBadge :rarity="dweller.rarity" size="sm" />
              </div>
            </div>
          </div>

          <div class="dweller-stats">
            <div class="stat-item" title="Strength">
              <span class="stat-label">S</span>
              <span class="stat-value">{{ dweller.strength }}</span>
            </div>
            <div class="stat-item" title="Perception">
              <span class="stat-label">P</span>
              <span class="stat-value">{{ dweller.perception }}</span>
            </div>
            <div class="stat-item" title="Endurance">
              <span class="stat-label">E</span>
              <span class="stat-value">{{ dweller.endurance }}</span>
            </div>
            <div class="stat-item" title="Charisma">
              <span class="stat-label">C</span>
              <span class="stat-value">{{ dweller.charisma }}</span>
            </div>
            <div class="stat-item" title="Intelligence">
              <span class="stat-label">I</span>
              <span class="stat-value">{{ dweller.intelligence }}</span>
            </div>
            <div class="stat-item" title="Agility">
              <span class="stat-label">A</span>
              <span class="stat-value">{{ dweller.agility }}</span>
            </div>
            <div class="stat-item" title="Luck">
              <span class="stat-label">L</span>
              <span class="stat-value">{{ dweller.luck }}</span>
            </div>
          </div>

          <div class="drag-indicator">
            <Icon icon="mdi:drag" class="h-5 w-5 text-gray-500" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.unassigned-dwellers-panel {
  background: rgba(0, 0, 0, 0.6);
  border: 1px solid var(--color-theme-primary);
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 1rem;
  font-family: 'Courier New', monospace;
}

.panel-header {
  margin-bottom: 1rem;
  border-bottom: 1px solid var(--color-theme-glow);
  padding-bottom: 0.5rem;
}

.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
}

.panel-title {
  color: var(--color-theme-primary);
  font-size: 1.25rem;
  font-weight: bold;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.count-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--color-theme-primary);
  color: var(--color-terminal-background);
  font-size: 0.875rem;
  font-weight: bold;
  min-width: 24px;
  height: 24px;
  border-radius: 12px;
  padding: 0 0.5rem;
}

.panel-subtitle {
  color: var(--color-theme-glow);
  font-size: 0.875rem;
  margin-top: 0.25rem;
}

.chip-group {
  display: flex;
  align-items: center;
  gap: 0.375rem;
}

.chip-group-label {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  color: var(--color-theme-primary);
  font-size: 0.6875rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  opacity: 0.7;
  white-space: nowrap;
}

.chip-group-icon {
  width: 1rem;
  height: 1rem;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.375rem 0.7rem;
  background: var(--color-surface-raised);
  border: 1px solid var(--color-theme-glow);
  border-radius: 6px;
  color: var(--color-theme-primary);
  font-size: 0.75rem;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  opacity: 0.6;
  transition: all 0.2s;
  white-space: nowrap;
}

.chip:hover {
  opacity: 0.8;
  background: var(--color-surface-hover);
  box-shadow: 0 0 8px var(--color-theme-glow);
}

.chip.active {
  opacity: 1;
  background: var(--color-surface-hover);
  border-color: var(--chip-accent, var(--color-theme-primary));
  box-shadow: 0 0 12px var(--color-theme-primary);
  font-weight: 600;
}

.chip-icon {
  width: 1rem;
  height: 1rem;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  color: var(--color-theme-glow);
  gap: 0.5rem;
  transition: all 0.3s ease;
  border: 2px dashed transparent;
  border-radius: 8px;
  min-height: 120px;
}

.empty-state.drop-zone-active {
  border-color: var(--color-theme-primary);
  background: var(--color-theme-glow);
  box-shadow: 0 0 20px var(--color-theme-glow);
}

.drop-message {
  color: var(--color-theme-primary);
  font-weight: bold;
  font-size: 1.125rem;
}

.dweller-grid-container {
  position: relative;
}

.drop-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--color-theme-glow);
  border: 3px dashed var(--color-theme-primary);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--color-theme-primary);
  font-size: 1.25rem;
  font-weight: bold;
  gap: 1rem;
  z-index: 10;
  pointer-events: none;
}

.dweller-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 0.875rem;
  max-height: 440px;
  overflow-y: auto;
  padding-right: 0.5rem;
}

.dweller-grid::-webkit-scrollbar {
  width: 8px;
}

.dweller-grid::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.3);
  border-radius: 4px;
}

.dweller-grid::-webkit-scrollbar-thumb {
  background: var(--color-theme-primary);
  border-radius: 4px;
}

.dweller-grid::-webkit-scrollbar-thumb:hover {
  background: var(--color-theme-accent);
}

.dweller-card {
  position: relative;
  background: rgba(0, 0, 0, 0.4);
  border: 1px solid var(--color-theme-glow);
  border-radius: 6px;
  padding: 1rem;
  cursor: grab;
  transition: all 0.2s ease;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.dweller-card:hover {
  border-color: var(--color-theme-primary);
  background: rgba(0, 0, 0, 0.6);
  transform: translateY(-2px);
  box-shadow: 0 4px 8px var(--color-theme-glow);
}

.dweller-card:active {
  cursor: grabbing;
  opacity: 0.7;
}

.dweller-top {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.dweller-avatar {
  position: relative;
  width: 56px;
  height: 56px;
  flex-shrink: 0;
}

.avatar-image {
  width: 56px;
  height: 56px;
  object-fit: cover;
  border-radius: 50%;
  border: 2px solid var(--rarity-ring, var(--color-theme-primary));
}


.dweller-heading {
  flex: 1;
  min-width: 0;
}

.dweller-name {
  color: var(--color-theme-primary);
  font-weight: bold;
  font-size: 0.9375rem;
  margin-bottom: 0.25rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding-right: 1.25rem;
}

.dweller-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.35rem 0.5rem;
  row-gap: 0.4rem;
}

.dweller-level {
  margin-right: 0.25rem;
  color: var(--color-theme-primary);
  opacity: 0.7;
  font-size: 0.6875rem;
  font-weight: 600;
  white-space: nowrap;
}

.dweller-stats {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 0.25rem;
  padding-top: 0.625rem;
  border-top: 1px solid var(--color-theme-glow);
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.125rem;
  font-size: 0.625rem;
}

.stat-label {
  color: var(--color-theme-primary);
  opacity: 0.6;
  font-weight: bold;
}

.stat-value {
  color: var(--color-theme-primary);
  font-weight: bold;
  font-size: 0.75rem;
}

.drag-indicator {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  opacity: 0.5;
}

.dweller-card:hover .drag-indicator {
  opacity: 1;
}
</style>
