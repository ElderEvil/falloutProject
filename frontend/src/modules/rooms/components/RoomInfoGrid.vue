<script setup lang="ts">
import { Icon } from '@iconify/vue'
import type { Room } from '../models/room'

interface Props {
  room: Room
  assignedDwellerCount: number
  dwellerCapacity: number
  abilityLabel: string | null
}

defineProps<Props>()
</script>

<template>
  <div class="section">
    <h3 class="section-title">
      <Icon icon="mdi:information" class="h-5 w-5" />
      Room Information
    </h3>
    <div class="info-grid">
      <div class="info-item">
        <span class="info-label">Dwellers:</span>
        <span class="info-value">{{ assignedDwellerCount }} / {{ dwellerCapacity }}</span>
      </div>
      <div class="info-item">
        <span class="info-label">Resource Capacity:</span>
        <span class="info-value">{{ room.capacity || 0 }}</span>
      </div>
      <div class="info-item">
        <span class="info-label">Room Size:</span>
        <span class="info-value"
            >{{ Math.ceil((room.size ?? room.size_min) / 3) }}x merged</span
        >
      </div>
      <div class="info-item">
        <span class="info-label">Position:</span>
        <span class="info-value">({{ room.coordinate_x }}, {{ room.coordinate_y }})</span>
      </div>
      <div v-if="room.ability" class="info-item">
        <span class="info-label">Required Stat:</span>
        <span class="info-value">{{ abilityLabel }}</span>
      </div>
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

.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.75rem;
}

.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid var(--color-theme-glow);
  border-radius: 4px;
}

.info-label {
  color: #aaa;
  font-size: 0.875rem;
  flex-shrink: 0;
}

.info-value {
  color: var(--color-theme-primary);
  font-weight: 600;
  text-align: right;
}
</style>
