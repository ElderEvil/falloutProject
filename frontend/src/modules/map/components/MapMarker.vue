<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'

interface Props {
  x: number
  y: number
  name: string
  type: 'home_vault' | 'origin' | 'visited' | 'discovery' | 'vault'
  selected?: boolean
  is_unlocked?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  selected: false,
  is_unlocked: true,
})

const emit = defineEmits<{
  (e: 'click'): void
}>()

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    emit('click')
  }
}

const typeIcons: Record<string, string> = {
  home_vault: 'mdi:home-city',
  origin: 'mdi:flag',
  visited: 'mdi:eye',
  discovery: 'mdi:compass',
  vault: 'mdi:radioactive',
}

const typeLabels: Record<string, string> = {
  home_vault: 'Home Vault',
  origin: 'Origin',
  visited: 'Visited',
  discovery: 'Discovery',
  vault: 'Vault Signal',
}

const icon = computed(() => typeIcons[props.type] ?? 'mdi:map-marker')
const label = computed(() => typeLabels[props.type] ?? props.type)
const isDiscovery = computed(() => props.type === 'discovery')
const isVault = computed(() => props.type === 'vault')

const isLocked = computed(
  () => !props.is_unlocked && props.type !== 'home_vault' && props.type !== 'vault'
)
const displayIcon = computed(() => (isLocked.value ? 'mdi:lock-question' : icon.value))
const displayLabel = computed(() => (isLocked.value ? 'Unknown Location' : props.name))

const tooltipText = computed(() => `${displayLabel.value} (${label.value})`)
</script>

<template>
  <g
    :transform="`translate(${x}, ${y})`"
    class="map-marker cursor-pointer"
    :class="{
      'marker-selected': selected,
      'marker-type-vault': isVault,
      'marker-locked': isLocked,
    }"
    tabindex="0"
    role="button"
    :aria-label="tooltipText"
    @click="emit('click')"
    @keydown="handleKeydown"
  >
    <!-- Native SVG tooltip. IMPORTANT: keep the <foreignObject> a DIRECT child
         of <g> - wrapping it in HTML elements (e.g. a tooltip <div>) collapses
         it to 0x0 in Chromium and the marker becomes invisible. -->
    <title>{{ tooltipText }}</title>

    <!-- Phosphor glow halo — atmospheric depth behind the icon -->
    <circle cx="0" cy="0" r="4.5" class="marker-halo" />

    <!-- Selection ring — animated when selected -->
    <circle v-if="selected" cx="0" cy="0" r="5.5" class="marker-select-ring" />

    <foreignObject x="-3" y="-3" width="6" height="6">
      <div
        v-bind="{ xmlns: 'http://www.w3.org/1999/xhtml' }"
        class="marker-icon"
        :class="{
          'marker-discovery': isDiscovery,
          'marker-vault': isVault,
        }"
      >
        <Icon :icon="displayIcon" class="h-full w-full" />
      </div>
    </foreignObject>
    <!-- Label: hidden by default, shown on hover/focus/selected via CSS -->
    <text class="marker-label" x="0" y="-4.2" text-anchor="middle" aria-hidden="true">{{
      displayLabel
    }}</text>
  </g>
</template>

<style scoped>
.map-marker {
  transition: transform 150ms ease;
}

/* Phosphor glow halo — subtle atmospheric depth */
.marker-halo {
  fill: var(--color-theme-primary);
  opacity: 0;
  transition: opacity 200ms ease;
}

.map-marker:hover .marker-halo,
.map-marker:focus-visible .marker-halo {
  opacity: 0.12;
}

.marker-type-vault .marker-halo {
  fill: var(--color-warning);
}

.marker-locked .marker-halo {
  fill: var(--color-theme-primary);
}

/* Selection ring — animated phosphor pulse */
.marker-select-ring {
  fill: none;
  stroke: var(--color-theme-primary);
  stroke-width: 0.2;
  opacity: 0.7;
  animation: select-pulse 2s ease-in-out infinite;
}

.marker-type-vault .marker-select-ring {
  stroke: var(--color-warning);
}

.map-marker:hover .marker-icon,
.map-marker:focus-visible .marker-icon {
  filter: drop-shadow(0 0 6px var(--color-theme-primary));
}

.map-marker:focus-visible {
  outline: 1px solid var(--color-theme-primary);
}

.marker-icon {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-theme-primary);
}

.marker-discovery {
  animation: discovery-pulse 2s ease-in-out infinite;
}

.marker-vault {
  color: var(--color-warning);
  opacity: 0.7;
}

.marker-locked {
  opacity: 0.5;
}

.marker-locked .marker-icon {
  stroke-dasharray: 4 2;
}

/* Label: hidden by default, visible on hover/focus/selected */
.marker-label {
  fill: var(--color-theme-primary);
  font-family: var(--font-family-mono);
  font-size: 2px;
  pointer-events: none;
  opacity: 0;
  transition: opacity 150ms ease;
  /* Paint stroke behind fill for a dark halo — keeps text readable */
  stroke: var(--color-surface);
  stroke-width: 0.3;
  paint-order: stroke fill;
}

.map-marker:hover .marker-label,
.map-marker:focus-visible .marker-label,
.map-marker.marker-selected .marker-label,
.map-marker.marker-locked .marker-label {
  opacity: 1;
}

/* Vault marker labels use warning color */
.marker-type-vault .marker-label {
  fill: var(--color-warning);
}

@keyframes discovery-pulse {
  0%,
  100% {
    opacity: 0.6;
    transform: scale(1);
  }
  50% {
    opacity: 1;
    transform: scale(1.15);
  }
}

@keyframes select-pulse {
  0%,
  100% {
    opacity: 0.7;
    r: 5.5;
  }
  50% {
    opacity: 0.3;
    r: 6.5;
  }
}
</style>
