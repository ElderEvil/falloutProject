<script setup lang="ts">
import { computed, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import { MARKER_TYPES } from '../models/markerTypeMeta'
import { DANGER_RAMP } from '../utils/dangerStyle'
import { useMapStore } from '../stores/map'
import {
  ATLAS_TERRAIN_CLASS,
  ATLAS_TERRAIN_LABEL,
  ATLAS_TERRAIN_ORDER,
} from '../utils/atlasProjection'

const legendItems = MARKER_TYPES

// Color = state, glyph = group identity (mirrors MapMarker.vue's state styling).
const MARKER_STATES = [
  { key: 'known', label: 'Known / active' },
  { key: 'unknown', label: 'Unknown / locked' },
  { key: 'cleared', label: 'Cleared' },
  { key: 'vault', label: 'Vault signal' },
  { key: 'explorer', label: 'Explorer' },
  { key: 'new', label: 'New discovery' },
] as const

// The legend overlays the map pane, so it stays collapsed on first view and
// remembers its state: a revealed area under it is otherwise invisible.
const LEGEND_COLLAPSED_KEY = 'map:legend-collapsed'

function readCollapsed(): boolean {
  try {
    return localStorage.getItem(LEGEND_COLLAPSED_KEY) !== 'false'
  } catch {
    return true
  }
}

const collapsed = ref(readCollapsed())

function toggleCollapsed() {
  collapsed.value = !collapsed.value
  try {
    localStorage.setItem(LEGEND_COLLAPSED_KEY, String(collapsed.value))
  } catch {
    // Storage unavailable (private mode, blocked cookies): the visible
    // state still toggles, it just won't persist.
  }
}

const mapStore = useMapStore()
const hasUnseen = computed(() => mapStore.hasUnseenDiscoveries)

// The active P3 site-type filter (same value the map/list receive): the chosen
// archetype stays lit, the rest recede. Non-interactive — the legend never
// drives the filter itself.
withDefaults(
  defineProps<{
    siteTypeFilter?: string | null
  }>(),
  { siteTypeFilter: null }
)

// Site-type archetypes actually present on this map, in catalog order.
const siteGroups = computed(() => {
  const present = new Set(mapStore.locations.map((loc) => loc.group_key).filter(Boolean))
  return mapStore.placeGroups.filter((group) => present.has(group.key))
})
</script>

<template>
  <div class="map-legend" role="complementary" aria-label="Map legend">
    <Button
      variant="ghost"
      size="xs"
      class="legend-toggle"
      :aria-expanded="!collapsed"
      @click="toggleCollapsed"
    >
      <span class="legend-title">MAP KEY</span>
      <Icon
        :icon="collapsed ? 'mdi:chevron-up' : 'mdi:chevron-down'"
        class="legend-toggle-icon"
      />
    </Button>
    <template v-if="!collapsed">
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

      <div class="legend-title legend-title-spaced">MARKER STATE</div>
      <div v-for="state in MARKER_STATES" :key="state.key" class="legend-item">
        <span class="legend-state-dot" :class="`legend-state-${state.key}`" />
        <span class="legend-label">{{ state.label }}</span>
      </div>

      <div class="legend-title legend-title-spaced">TERRAIN</div>
      <div v-for="terrain in ATLAS_TERRAIN_ORDER" :key="terrain" class="legend-terrain">
        <span class="legend-swatch" :class="ATLAS_TERRAIN_CLASS[terrain]" />
        <span class="legend-label">{{ ATLAS_TERRAIN_LABEL[terrain] }}</span>
      </div>

      <div class="legend-title legend-title-spaced">DANGER</div>
      <div v-for="entry in DANGER_RAMP" :key="entry.level" class="legend-danger">
        <span class="legend-danger-swatch" :class="`legend-danger-${entry.level}`" />
        <span class="legend-label">{{ entry.label }}</span>
      </div>

      <template v-if="siteGroups.length">
        <div class="legend-title legend-title-spaced">SITE TYPES</div>
        <div
          v-for="group in siteGroups"
          :key="group.key"
          class="legend-item legend-site-item"
          :class="{
            'legend-site-selected': siteTypeFilter === group.key,
            'legend-site-dimmed': siteTypeFilter !== null && siteTypeFilter !== group.key,
          }"
        >
          <span class="legend-icon-wrapper">
            <Icon :icon="group.icon" class="legend-icon" />
          </span>
          <span class="legend-label">{{ group.label }}</span>
        </div>
      </template>
    </template>
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
  text-transform: uppercase;
}

.legend-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  margin-bottom: 4px;
  padding: 0;
  border: none;
  background: none;
  color: inherit;
  font: inherit;
  cursor: pointer;
  pointer-events: auto;
}

.legend-toggle-icon {
  width: 12px;
  height: 12px;
  opacity: 0.7;
}

.legend-title-spaced {
  margin-top: 6px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  line-height: 1.6;
}

.legend-terrain {
  display: flex;
  align-items: center;
  gap: 6px;
  line-height: 1.6;
}

.legend-danger {
  display: flex;
  align-items: center;
  gap: 6px;
  line-height: 1.6;
}

.legend-danger-swatch {
  width: 12px;
  height: 12px;
  flex-shrink: 0;
  border-radius: 50%;
  border: 1px solid color-mix(in srgb, var(--color-theme-primary) 40%, transparent);
}

.legend-danger-low {
  background-color: var(--color-success);
}

.legend-danger-medium {
  background-color: var(--color-warning);
}

.legend-danger-high {
  background-color: var(--color-danger);
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

.legend-swatch {
  width: 12px;
  height: 12px;
  flex-shrink: 0;
  border: 1px solid color-mix(in srgb, var(--color-theme-primary) 40%, transparent);
  border-radius: 2px;
}

.legend-label {
  white-space: nowrap;
}

/* Marker state dots mirror MapMarker.vue's fill/opacity/animation so the legend
   is a direct color key for "color = state". */
.legend-state-dot {
  width: 10px;
  height: 10px;
  flex-shrink: 0;
  border: 1px solid color-mix(in srgb, var(--color-theme-primary) 40%, transparent);
  border-radius: 50%;
  background: var(--color-theme-primary);
}

.legend-state-unknown {
  filter: grayscale(1);
  opacity: 0.5;
}

.legend-state-cleared {
  opacity: 0.45;
}

.legend-state-vault {
  background: var(--color-warning);
  border-color: color-mix(in srgb, var(--color-warning) 40%, transparent);
}

.legend-state-explorer {
  background: var(--color-theme-accent);
  border-color: color-mix(in srgb, var(--color-theme-accent) 40%, transparent);
}

/* An unseen discovery pulses in the primary colour on the map, so its key dot
   pulses in step; the explorer marker (above) is a static accent. */
.legend-state-new {
  animation: legend-pulse 2s ease-in-out infinite;
}

.legend-vault .legend-icon {
  color: var(--color-warning);
  opacity: 0.85;
}

/* P3 site-type filter: keep the selected archetype lit and recede the rest so
   the key mirrors the filtered map without becoming interactive. */
.legend-site-dimmed {
  opacity: 0.35;
}

.legend-site-selected .legend-icon-wrapper {
  background: var(--color-theme-glow);
  border-radius: 2px;
  box-shadow: 0 0 5px var(--color-theme-glow);
}

.legend-site-selected .legend-label {
  text-shadow: 0 0 5px var(--color-theme-glow);
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
  .legend-unseen .legend-icon,
  .legend-state-new {
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

  .legend-danger-swatch {
    width: 8px;
    height: 8px;
  }
}
</style>
