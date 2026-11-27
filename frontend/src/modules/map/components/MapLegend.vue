<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { PURPOSE_META } from '../models/purposeMeta'

const states = [
  { label: 'Unscouted', hint: 'dashed', icon: 'mdi:map-marker-outline' },
  { label: 'Cleared', hint: 'tick', icon: 'mdi:check' },
  { label: 'Cooldown', hint: 'clock', icon: 'mdi:clock-outline' },
  { label: 'Exploring', hint: 'pulse', icon: 'mdi:circle-double' },
]

const signals = [
  { label: 'Vault signal', hint: 'not a target', icon: 'mdi:radioactive' },
  { label: 'Expedition site', hint: 'party goal', icon: 'mdi:map-marker-star' },
  { label: 'Party / cluster', hint: 'counted', icon: 'mdi:circle-multiple-outline' },
]
</script>

<template>
  <section
    class="map-legend border-b border-theme-primary/20 p-3 text-xs text-theme-primary"
    role="region"
    aria-label="Map legend"
  >
    <section class="legend-block">
      <h3>Purpose</h3>
      <div class="legend-grid">
        <span v-for="entry in PURPOSE_META" :key="entry.purpose" class="legend-item">
          <svg viewBox="0 0 10 10" class="size-3.5 shrink-0" aria-hidden="true">
            <circle v-if="entry.shape === 'circle'" cx="5" cy="5" r="4" class="legend-shape" />
            <circle
              v-else-if="entry.shape === 'ring'"
              cx="5"
              cy="5"
              r="4"
              class="legend-shape ring"
            />
            <path
              v-else-if="entry.shape === 'diamond'"
              d="M5 1 9 5 5 9 1 5Z"
              class="legend-shape"
            />
            <rect v-else x="1.2" y="1.2" width="7.6" height="7.6" rx="1.4" class="legend-shape" />
          </svg>
          <span class="font-medium">{{ entry.label }}</span>
          <span class="hint text-theme-primary/65">{{ entry.hint }}</span>
        </span>
      </div>
    </section>

    <section class="legend-block">
      <h3>Status</h3>
      <div class="legend-grid">
        <span v-for="state in states" :key="state.label" class="legend-item">
          <Icon :icon="state.icon" class="size-4 shrink-0" :ariaHidden="true" />
          <span class="font-medium">{{ state.label }}</span>
          <span class="hint text-theme-primary/65">{{ state.hint }}</span>
        </span>
      </div>
    </section>

    <section class="legend-block">
      <h3>Signals</h3>
      <div class="legend-grid">
        <span v-for="signal in signals" :key="signal.label" class="legend-item">
          <Icon :icon="signal.icon" class="size-4 shrink-0" :ariaHidden="true" />
          <span class="font-medium">{{ signal.label }}</span>
          <span class="hint text-theme-primary/65">{{ signal.hint }}</span>
        </span>
      </div>
    </section>

    <p class="mt-3 leading-relaxed text-theme-primary/65">
      The glyph inside a marker names the site type; the body shape names what it is for.
    </p>
  </section>
</template>

<style scoped>
.legend-block + .legend-block {
  margin-top: 0.75rem;
}

h3 {
  margin-bottom: 0.375rem;
  font-size: 0.6875rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  opacity: 0.75;
}

.legend-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 0.125rem 0.75rem;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  min-width: 0;
}

/* The hint is a trailing hint, not a sentence: one line, clipped rather than wrapped. */
.legend-item .hint::before {
  content: '· ';
  opacity: 0.6;
}

.legend-item .hint {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.legend-shape {
  fill: color-mix(in srgb, var(--color-terminal-background) 90%, transparent);
  stroke: currentColor;
  stroke-width: 1.1;
}

.legend-shape.ring {
  fill: none;
  stroke-width: 1.2;
}
</style>
