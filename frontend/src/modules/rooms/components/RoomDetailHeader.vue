<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import type { Room } from '../models/room'

interface Props {
  room: Room
  resourceIcon: string
  justUpgraded: boolean
}

const props = defineProps<Props>()
const roomSizeText = computed(() => `${Math.ceil((props.room.size ?? props.room.size_min) / 3)}× merged`)
</script>

<template>
  <div class="modal-header">
    <div class="header-content">
      <div class="header-identity">
        <h2 class="room-title">
          <Icon :icon="resourceIcon" class="room-icon" />
          {{ room.name }}
        </h2>
        <div class="header-metadata">
          <span class="metadata-item">{{ room.category }} Room</span>
          <span class="metadata-divider">&middot;</span>
          <span class="metadata-item" :class="{ 'tier-upgraded': justUpgraded }">Tier {{ room.tier }}</span>
          <span v-if="room.ability" class="metadata-divider">&middot;</span>
          <span v-if="room.ability" class="metadata-item">Requires: {{ room.ability.charAt(0) }}</span>
        </div>
      </div>

      <div class="room-facts" aria-label="Room information">
        <span class="room-fact"><span>Capacity</span><strong>{{ room.capacity || 0 }}</strong></span>
        <span class="room-fact"><span>Size</span><strong>{{ roomSizeText }}</strong></span>
        <span class="room-fact"><span>Position</span><strong>({{ room.coordinate_x }}, {{ room.coordinate_y }})</strong></span>
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
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.header-identity {
  min-width: 0;
}

.room-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0;
  color: var(--color-theme-primary);
  font-size: 1.125rem;
  font-weight: bold;
}

.room-icon {
  width: 1.25rem;
  height: 1.25rem;
  color: var(--color-terminal-green);
}

.header-metadata {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--color-gray-300);
  font-size: 0.75rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.metadata-item {
  color: var(--color-gray-300);
}

.metadata-divider {
  color: var(--color-gray-600);
}

.room-facts {
  display: flex;
  align-items: center;
  gap: 0.625rem;
  flex-shrink: 0;
  text-align: right;
  white-space: nowrap;
}

.room-fact {
  display: inline-flex;
  align-items: baseline;
  justify-content: flex-end;
  gap: 0.25rem;
  color: var(--color-gray-300);
  font-size: 0.75rem;
  line-height: 1.2;
}

.room-fact + .room-fact {
  padding-left: 0.625rem;
  border-left: 1px solid var(--color-theme-glow);
}

.room-fact > span {
  color: var(--color-gray-400);
  font-size: 0.625rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.room-fact strong {
  color: var(--color-theme-primary);
  font-weight: 600;
}

.tier-upgraded {
  animation: tier-upgrade-pulse 1s ease-out;
  color: var(--color-terminal-green) !important;
  font-weight: bold;
}

@keyframes tier-upgrade-pulse {
  0% { transform: scale(1); filter: drop-shadow(0 0 0 var(--color-theme-glow)); }
  25% { transform: scale(1.2); filter: drop-shadow(0 0 8px var(--color-theme-glow)); }
  50% { transform: scale(1.1); filter: drop-shadow(0 0 12px var(--color-theme-glow)); }
  75% { transform: scale(1.15); filter: drop-shadow(0 0 8px var(--color-theme-glow)); }
  100% { transform: scale(1); filter: drop-shadow(0 0 4px var(--color-theme-glow)); }
}

@media (max-width: 680px) {
  .header-content {
    align-items: flex-start;
    flex-direction: column;
  }

  .room-facts {
    width: 100%;
    flex-wrap: wrap;
    text-align: left;
    white-space: normal;
  }

  .room-fact {
    justify-content: flex-start;
  }
}
</style>
