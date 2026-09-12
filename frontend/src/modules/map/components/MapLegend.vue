<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { MARKER_TYPES } from '../models/markerTypeMeta'
import { useMapStore } from '../stores/map'

const legendItems = MARKER_TYPES

const mapStore = useMapStore()
const hasUnseen = computed(() => mapStore.hasUnseenDiscoveries)
</script>

<template>
  <div class="map-legend" role="complementary" aria-label="Map legend">
    <div class="legend-title">MAP KEY</div>
    <div v-for="item in legendItems" :key="item.type" class="legend-item">
      <span
        class="legend-icon-wrapper"
        :class="{
          'legend-vault': item.type === 'vault',
          'legend-unseen': item.type === 'discovery' && hasUnseen,
        }"
      >
        <Icon :icon="item.icon" class="legend-icon" />
      </span>
      <span class="legend-label">{{ item.label }}</span>
    </div>
  </div>
</template>

<style scoped>
.map-legend {
  position: absolute;
  bottom: 8px;
  left: 8px;
  z-index: 10;
  padding: 6px 8px;
  background-color: color-mix(in srgb, var(--color-surface) 85%, transparent);
  border: 1px solid var(--color-theme-primary);
  border-radius: 2px;
  box-shadow: 0 0 6px var(--color-theme-glow);
  font-family: var(--font-family-mono);
  font-size: 12px;
  color: var(--color-theme-primary);
  pointer-events: none;
  user-select: none;
}

.legend-title {
  font-size: 9px;
  letter-spacing: 0.1em;
  opacity: 0.6;
  margin-bottom: 4px;
  text-transform: uppercase;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  line-height: 1.6;
}

.legend-icon-wrapper {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

.legend-icon {
  width: 12px;
  height: 12px;
  color: var(--color-theme-primary);
}

.legend-label {
  white-space: nowrap;
}

.legend-vault .legend-icon {
  color: var(--color-warning);
  opacity: 0.85;
}

.legend-unseen .legend-icon {
  animation: legend-pulse 2s ease-in-out infinite;
}

@keyframes legend-pulse {
  0%,
  100% {
    opacity: 0.5;
  }
  50% {
    opacity: 1;
  }
}

@media (prefers-reduced-motion: reduce) {
  .legend-unseen .legend-icon {
    animation: none;
  }
}

@media (max-width: 768px) {
  .map-legend {
    font-size: 8px;
    padding: 4px 6px;
    bottom: 4px;
    left: 4px;
  }

  .legend-icon-wrapper {
    width: 10px;
    height: 10px;
  }

  .legend-icon {
    width: 8px;
    height: 8px;
  }
}
</style>
