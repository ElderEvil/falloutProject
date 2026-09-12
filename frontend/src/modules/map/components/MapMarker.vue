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
  unseen?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  selected: false,
  is_unlocked: true,
  unseen: false,
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
const shouldPulse = computed(() => isDiscovery.value && !isLocked.value && props.unseen)

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
    <circle v-if="selected" class="marker-select-ring" r="4.2" />
    <circle v-if="selected" class="marker-select-ping" r="4.2" />
    <foreignObject x="-3.5" y="-3.5" width="7" height="7">
      <div
        v-bind="{ xmlns: 'http://www.w3.org/1999/xhtml' }"
        class="marker-icon"
        :class="{
          'marker-discovery': shouldPulse,
          'marker-vault': isVault,
        }"
      >
        <Icon :icon="displayIcon" class="h-full w-full" />
      </div>
    </foreignObject>
    <!-- Label: hidden by default, shown on hover/focus/selected via CSS -->
    <text class="marker-label" x="0" y="-3.4" text-anchor="middle" aria-hidden="true">{{
      displayLabel
    }}</text>
  </g>
</template>

<style scoped>
.map-marker {
  transition: transform 150ms ease;
}

.map-marker:hover .marker-icon,
.map-marker:focus-visible .marker-icon {
  filter: drop-shadow(0 0 6px var(--color-theme-primary));
}

.map-marker:focus-visible {
  outline: none;
  filter: drop-shadow(0 0 4px var(--color-theme-primary));
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

.marker-select-ring {
  fill: none;
  stroke: var(--color-theme-primary);
  stroke-width: 0.4;
  opacity: 0.9;
  pointer-events: none;
}

.marker-select-ping {
  fill: none;
  stroke: var(--color-theme-primary);
  stroke-width: 0.4;
  pointer-events: none;
  transform-box: fill-box;
  transform-origin: center;
  animation: select-ping 600ms ease-out 1;
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
  font-size: 2.4px;
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

@keyframes select-ping {
  0% {
    opacity: 0.9;
    transform: scale(0.6);
  }
  100% {
    opacity: 0;
    transform: scale(1.8);
  }
}
</style>
