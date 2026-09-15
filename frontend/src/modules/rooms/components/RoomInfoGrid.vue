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
  <section class="room-summary" aria-label="Room summary">
    <details class="system-details">
      <summary>
        <span class="details-title">
          <Icon icon="mdi:information-outline" />
          System details
        </span>
        <span class="details-toggle">
          Inspect
          <Icon icon="mdi:chevron-down" />
        </span>
      </summary>
      <div class="details-readout">
        <span>Room Size: {{ roomSizeText }}</span>
        <span>Position: ({{ room.coordinate_x }}, {{ room.coordinate_y }})</span>
        <span v-if="room.ability">Focus: {{ abilityLabel }}</span>
      </div>
    </details>
  </section>
</template>

<style scoped>
.room-summary {
  background: var(--color-surface-sunken);
  border-block: 1px solid color-mix(in srgb, var(--color-theme-primary) 25%, transparent);
}

.system-details summary,
.details-readout {
  color: color-mix(in srgb, var(--color-theme-primary) 58%, transparent);
  font-size: 0.625rem;
  letter-spacing: 0.09em;
  text-transform: uppercase;
}

.system-details {
  display: block;
}

.system-details summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  cursor: pointer;
  list-style: none;
  padding: 0.45rem 0.75rem;
  background: color-mix(in srgb, var(--color-theme-primary) 6%, transparent);
  border-block: 1px solid color-mix(in srgb, var(--color-theme-primary) 18%, transparent);
}

.system-details summary::-webkit-details-marker {
  display: none;
}

.details-title,
.details-toggle {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.details-toggle {
  color: var(--color-theme-primary);
  font-weight: 700;
}

.system-details summary :deep(svg) {
  height: 0.75rem;
  width: 0.75rem;
}

.details-toggle :deep(svg) {
  transition: transform 150ms ease;
}

.system-details[open] .details-toggle :deep(svg) {
  transform: rotate(180deg);
}

.system-details summary:hover,
.system-details summary:focus-visible {
  background: color-mix(in srgb, var(--color-theme-primary) 12%, transparent);
  color: var(--color-theme-primary);
}

.system-details summary:focus-visible {
  outline: 1px solid var(--color-theme-primary);
  outline-offset: -1px;
}

.details-readout {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  padding: 0 0.75rem 0.55rem;
}

</style>
