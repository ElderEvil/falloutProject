<script setup lang="ts">
import { Icon } from '@iconify/vue'

interface LegendItem {
  type: string
  icon: string
  label: string
  colorClass: string
}

const legendItems: LegendItem[] = [
  {
    type: 'home_vault',
    icon: 'mdi:home-city',
    label: 'Home Vault',
    colorClass: 'legend-color-home',
  },
  { type: 'origin', icon: 'mdi:flag', label: 'Origin', colorClass: 'legend-color-origin' },
  { type: 'visited', icon: 'mdi:eye', label: 'Visited', colorClass: 'legend-color-visited' },
  {
    type: 'discovery',
    icon: 'mdi:compass',
    label: 'Discovery',
    colorClass: 'legend-color-discovery',
  },
  {
    type: 'vault',
    icon: 'mdi:radioactive',
    label: 'Vault Signal',
    colorClass: 'legend-color-vault',
  },
]
</script>

<template>
  <div class="map-legend" role="complementary" aria-label="Map legend">
    <div class="legend-title">MAP KEY</div>
    <div v-for="item in legendItems" :key="item.type" class="legend-item">
      <span class="legend-icon-wrapper" :class="item.colorClass">
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
  font-size: 10px;
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
}

.legend-label {
  white-space: nowrap;
}

/* Color variants matching MapMarker type colors */
.legend-color-home .legend-icon,
.legend-color-origin .legend-icon,
.legend-color-visited .legend-icon,
.legend-color-discovery .legend-icon {
  color: var(--color-theme-primary);
}

.legend-color-vault .legend-icon {
  color: var(--color-warning);
  opacity: 0.85;
}

.legend-color-discovery .legend-icon {
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
</style>
