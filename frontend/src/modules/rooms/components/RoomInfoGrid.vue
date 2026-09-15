<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { computed } from 'vue'
import type { Room } from '../models/room'

interface Props {
  room: Room
  abilityLabel: string | null
  assignedDwellerCount: number
  dwellerCapacity: number
}

const props = defineProps<Props>()

const roomSizeText = computed(
  () => `${Math.ceil((props.room.size ?? props.room.size_min) / 3)}x merged`
)
</script>

<template>
  <section class="room-summary" aria-label="Room summary">
    <div class="summary-cell">
      <span class="summary-label">Crew</span>
      <strong class="summary-value">{{ assignedDwellerCount }}/{{ dwellerCapacity }}</strong>
    </div>
    <div v-if="room.ability" class="summary-cell">
      <span class="summary-label">Focus</span>
      <strong class="summary-value">{{ abilityLabel }}</strong>
    </div>
    <div class="summary-cell">
      <span class="summary-label">Capacity</span>
      <strong class="summary-value">{{ room.capacity || 0 }}</strong>
    </div>
    <details class="system-details">
      <summary>
        <Icon icon="mdi:information-outline" />
        System details
      </summary>
      <div class="details-readout">
        <span>Room Size: {{ roomSizeText }}</span>
        <span>Position: ({{ room.coordinate_x }}, {{ room.coordinate_y }})</span>
        <span v-if="room.ability">Required Stat: {{ abilityLabel }}</span>
      </div>
    </details>
  </section>
</template>

<style scoped>
.room-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  background: var(--color-surface-sunken);
  border-block: 1px solid color-mix(in srgb, var(--color-theme-primary) 25%, transparent);
}

.summary-cell {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
  min-width: 0;
  padding: 0.55rem 0.75rem;
  border-right: 1px solid color-mix(in srgb, var(--color-theme-primary) 20%, transparent);
}

.summary-label,
.system-details summary,
.details-readout {
  color: color-mix(in srgb, var(--color-theme-primary) 58%, transparent);
  font-size: 0.625rem;
  letter-spacing: 0.09em;
  text-transform: uppercase;
}

.summary-value {
  overflow: hidden;
  color: var(--color-theme-primary);
  font-size: 0.875rem;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.system-details {
  grid-column: 1 / -1;
  border-top: 1px solid color-mix(in srgb, var(--color-theme-primary) 20%, transparent);
}

.system-details summary {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  cursor: pointer;
  list-style: none;
  padding: 0.45rem 0.75rem;
}

.system-details summary::-webkit-details-marker {
  display: none;
}

.system-details summary :deep(svg) {
  height: 0.75rem;
  width: 0.75rem;
}

.details-readout {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  padding: 0 0.75rem 0.55rem;
}

@media (max-width: 480px) {
  .room-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .summary-cell:nth-child(2) {
    border-right: 0;
  }
}
</style>
