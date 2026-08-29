<script setup lang="ts">
import { Icon } from '@iconify/vue'
import type { DwellerShort, SpecialKey } from '@/modules/dwellers/models/dweller'
import DwellerAgeBadge from '@/modules/dwellers/components/DwellerAgeBadge.vue'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'

interface Props {
  assignedDwellers: DwellerShort[]
  dwellerCapacity: number
  ability: string | null
}

const props = defineProps<Props>()

const emit = defineEmits<{
  dwellerClick: [dwellerId: string]
}>()

const getDwellerStatValue = (dweller: DwellerShort, ability: string) => {
  const value = dweller[ability.toLowerCase() as SpecialKey]
  return typeof value === 'number' ? value : 0
}
</script>

<template>
  <div class="section dweller-section">
    <div class="staffing-header">
      <h3 class="section-title dweller-section-title">
        <Icon icon="mdi:account-group" class="h-5 w-5" />
        Staffing
      </h3>
      <span class="staffing-summary">{{ assignedDwellers.length }} / {{ dwellerCapacity }} staffed</span>
    </div>
    <div v-if="assignedDwellers.length > 0" class="dwellers-list">
      <button
        v-for="dweller in assignedDwellers"
        :key="dweller.id"
        type="button"
        class="dweller-card clickable"
        @click="emit('dwellerClick', dweller.id)"
      >
        <DwellerPortrait
          :thumbnail-url="dweller.thumbnail_url"
          :alt="`${dweller.first_name} ${dweller.last_name ?? ''}`"
          image-class="dweller-portrait"
          fallback-class="h-10 w-10 icon-primary"
        />
        <div class="dweller-info">
          <div class="dweller-name">{{ dweller.first_name }} {{ dweller.last_name }}</div>
          <DwellerAgeBadge :age-group="dweller.age_group" size="sm" />
          <div class="dweller-level">Level {{ dweller.level }}</div>
        </div>
        <div v-if="ability" class="dweller-stat">
          <span class="stat-label">{{ ability.charAt(0) }}</span>
          <span class="stat-value">{{ getDwellerStatValue(dweller, ability) }}</span>
        </div>
      </button>
    </div>
    <div v-else class="empty-state">
      <Icon icon="mdi:account-off" class="h-12 w-12 opacity-50" />
      <p>No dwellers assigned to this room</p>
      <p class="text-sm">Drag dwellers from the sidebar to assign them</p>
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

.staffing-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.dweller-section-title {
  font-weight: 700;
}

.staffing-summary {
  color: var(--color-theme-primary);
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  white-space: nowrap;
}

.dwellers-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 0.5rem;
  max-height: 180px;
  overflow-y: auto;
}

.dweller-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
  width: 100%;
  padding: 0.6rem 0.75rem;
  background: var(--color-surface-sunken);
  border: 1px solid var(--color-theme-glow);
  color: inherit;
  font: inherit;
  text-align: left;
  border-radius: 4px;
  transition: all 0.2s;
}

.dweller-portrait {
  width: 48px;
  height: 48px;
  border-radius: 4px;
  object-fit: cover;
  flex-shrink: 0;
  border: 1px solid var(--color-theme-glow);
}

.dweller-info {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  flex: 1;
  min-width: 0;
}

.dweller-name {
  font-weight: 600;
  font-size: 0.9375rem;
  color: var(--color-theme-primary);
  overflow-wrap: break-word;
}

.dweller-level {
  font-size: 0.75rem;
  color: var(--color-gray-400);
}

.dweller-card.clickable {
  cursor: pointer;
}

.dweller-card.clickable:hover,
.dweller-card.clickable:focus-visible {
  background: var(--color-surface-hover);
  border-color: var(--color-theme-primary);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px var(--color-theme-glow);
  outline: none;
}

.dweller-stat {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  background: var(--color-surface-sunken);
  border-radius: 4px;
  flex-shrink: 0;
  min-width: 60px;
}

.dweller-stat .stat-label {
  font-weight: bold;
  color: var(--color-warning);
  font-size: 0.875rem;
}

.dweller-stat .stat-value {
  font-size: 1.125rem;
  font-weight: bold;
  color: var(--color-theme-primary);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem 1rem;
  color: var(--color-gray-500);
  text-align: center;
}

.empty-state p {
  margin: 0.5rem 0;
}
</style>
