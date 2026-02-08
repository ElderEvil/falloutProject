<script setup lang="ts">
import { Icon } from '@iconify/vue'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'

interface Props {
  assignedDwellers: DwellerShort[]
  ability: string | null
}

const props = defineProps<Props>()

const emit = defineEmits<{
  dwellerClick: [dwellerId: string]
}>()

const getDwellerStatValue = (dweller: DwellerShort, ability: string) => {
  const key = ability.toLowerCase() as
    | 'strength'
    | 'perception'
    | 'endurance'
    | 'charisma'
    | 'intelligence'
    | 'agility'
    | 'luck'
  const value = dweller[key]
  return typeof value === 'number' ? value : 0
}
</script>

<template>
  <div class="section dweller-section">
    <h3 class="section-title dweller-section-title">
      <Icon icon="mdi:account-group" class="h-5 w-5" />
      Dweller Details ({{ assignedDwellers.length }})
    </h3>
    <div v-if="assignedDwellers.length > 0" class="dwellers-list">
      <div
        v-for="dweller in assignedDwellers"
        :key="dweller.id"
        class="dweller-card clickable"
        @click="emit('dwellerClick', dweller.id)"
      >
        <div class="dweller-info">
          <div class="dweller-name">{{ dweller.first_name }} {{ dweller.last_name }}</div>
          <div class="dweller-level">Level {{ dweller.level }}</div>
        </div>
        <div v-if="ability" class="dweller-stat">
          <span class="stat-label">{{ ability.charAt(0) }}</span>
          <span class="stat-value">{{ getDwellerStatValue(dweller, ability) }}</span>
        </div>
      </div>
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
  gap: 1rem;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--color-theme-primary);
  margin: 0;
}

.dweller-section {
  margin-top: 2rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--color-theme-glow);
}

.dweller-section-title {
  font-weight: 700;
}

.dwellers-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 0.75rem;
  max-height: 300px;
  overflow-y: auto;
}

.dweller-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid var(--color-theme-glow);
  border-radius: 4px;
  transition: all 0.2s;
}

.dweller-card.clickable {
  cursor: pointer;
}

.dweller-card.clickable:hover {
  background: rgba(0, 0, 0, 0.5);
  border-color: var(--color-theme-primary);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px var(--color-theme-glow);
}

.dweller-info {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  flex: 1;
  min-width: 0;
}

.dweller-name {
  font-weight: 600;
  color: var(--color-theme-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dweller-level {
  font-size: 0.75rem;
  color: #aaa;
}

.dweller-stat {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 4px;
  flex-shrink: 0;
  min-width: 60px;
}

.dweller-stat .stat-label {
  font-weight: bold;
  color: #fbbf24;
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
  color: #888;
  text-align: center;
}

.empty-state p {
  margin: 0.5rem 0;
}
</style>
