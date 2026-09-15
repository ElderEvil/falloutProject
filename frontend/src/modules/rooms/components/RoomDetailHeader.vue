<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import type { Room } from '../models/room'

interface Props {
  room: Room
  resourceIcon: string
}

const props = defineProps<Props>()
const roomSizeText = computed(() => `${props.room.size ?? props.room.size_min}U`)
</script>

<template>
  <div class="modal-header">
    <div class="header-content">
      <h2 class="room-title terminal-glow">
        <Icon :icon="resourceIcon" class="room-icon" />
        {{ room.name }}
      </h2>
      <div class="header-metadata" aria-label="Room information">
        <span class="metadata-item">{{ room.category }} Room</span>
        <span class="metadata-divider">&middot;</span>
        <span class="metadata-item">Tier {{ room.tier }}</span>
        <span v-if="room.ability" class="metadata-divider">&middot;</span>
        <span v-if="room.ability" class="metadata-item">Requires: {{ room.ability.charAt(0) }}</span>
        <span class="metadata-divider">&middot;</span>
        <span class="metadata-item">Capacity: {{ room.capacity || 0 }}</span>
        <span class="metadata-divider">&middot;</span>
        <span class="metadata-item">Size: {{ roomSizeText }}</span>
        <span class="metadata-divider">&middot;</span>
        <span class="metadata-item">Position: ({{ room.coordinate_x }}, {{ room.coordinate_y }})</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-header {
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--color-theme-glow);
}

.header-content {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.room-title {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin: 0;
  color: var(--color-theme-primary);
  font-size: 1.5rem;
  font-weight: bold;
  letter-spacing: 0.04em;
  line-height: 1.15;
}

.room-icon {
  width: 1.5rem;
  height: 1.5rem;
  color: var(--color-terminal-green);
}

.header-metadata {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: color-mix(in srgb, var(--color-theme-primary) 60%, transparent);
  font-size: 0.75rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  white-space: nowrap;
}

.metadata-item {
  color: inherit;
}

.metadata-divider {
  color: color-mix(in srgb, var(--color-theme-primary) 35%, transparent);
}

@media (max-width: 720px) {
  .header-metadata {
    white-space: normal;
  }
}

</style>
