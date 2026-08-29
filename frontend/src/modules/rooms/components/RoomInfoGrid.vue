<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { computed } from 'vue'
import type { Room } from '../models/room'

interface Props {
  room: Room
  abilityLabel: string | null
}

const props = defineProps<Props>()

const roomSizeText = computed(
  () => `${Math.ceil((props.room.size ?? props.room.size_min) / 3)}x merged`
)
</script>

<template>
  <div class="section">
    <h3 class="section-title">
      <Icon icon="mdi:information" class="h-5 w-5" />
      Room Information
    </h3>
    <div class="info-grid">

      <div class="info-item">
        <span class="info-label">Resource Capacity:</span>
        <span class="info-value">{{ room.capacity || 0 }}</span>
      </div>
      <div class="info-item">
        <span class="info-label">Room Size:</span>
        <span class="info-value">{{ roomSizeText }}</span>
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

.info-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.5rem;
}

.info-item {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 0.15rem;
  padding: 0.5rem 0.6rem;
  background: var(--color-surface-sunken);
  border: 1px solid var(--color-theme-glow);
  border-radius: 4px;
}

.info-label {
  color: var(--color-gray-400);
  font-size: 0.6875rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.info-value {
  color: var(--color-theme-primary);
  font-weight: 600;
  font-size: 0.9375rem;
}
</style>
