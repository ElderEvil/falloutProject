<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { markerTypeMeta, type MarkerType } from '../models/markerTypeMeta'

interface Props {
  x: number
  y: number
  name: string
  type: MarkerType
  selected?: boolean
  is_unlocked?: boolean
  unseen?: boolean
  icon?: string
  label?: string
  cleared?: boolean
  exploring?: boolean
  status?: string
  interactive?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  selected: false,
  is_unlocked: true,
  unseen: false,
  cleared: false,
  exploring: false,
  interactive: true,
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

function handleClick() {
  if (props.interactive) emit('click')
}

const meta = computed(() => markerTypeMeta(props.type))
const icon = computed(() => props.icon ?? meta.value.icon)
const label = computed(() => props.label ?? meta.value.label)
const isDiscovery = computed(() => props.type === 'discovery')
const isVault = computed(() => props.type === 'vault')

const isLocked = computed(
  () => !props.is_unlocked && props.type !== 'home_vault' && props.type !== 'vault'
)
const displayIcon = computed(() => (isLocked.value ? 'mdi:lock-question' : icon.value))
const displayLabel = computed(() => (isLocked.value ? 'Unknown Location' : props.name))
const shouldPulse = computed(() => isDiscovery.value && !isLocked.value && props.unseen)

const tooltipText = computed(() => {
  const base = `${displayLabel.value} (${label.value})`
  return props.status ? `${base} — ${props.status}` : base
})
</script>

<template>
  <g
    :transform="`translate(${x}, ${y})`"
    class="map-marker"
    :class="{
      'cursor-pointer': interactive,
      'marker-non-interactive': !interactive,
      'marker-selected': selected,
      'marker-type-vault': isVault,
      'marker-locked': isLocked,
      'marker-cleared': cleared,
      'marker-explorer': type === 'explorer',
    }"
    :tabindex="interactive ? 0 : undefined"
    :role="interactive ? 'button' : undefined"
    :aria-label="interactive ? tooltipText : undefined"
    @click="handleClick"
    @keydown="handleKeydown"
  >
    <!-- Native SVG tooltip. IMPORTANT: keep the <foreignObject> a DIRECT child
         of <g> - wrapping it in HTML elements (e.g. a tooltip <div>) collapses
         it to 0x0 in Chromium and the marker becomes invisible. -->
    <title>{{ tooltipText }}</title>
    <circle v-if="selected" class="marker-select-ring" r="3.1" />
    <circle v-if="selected" class="marker-select-ping" r="3.1" />
    <circle v-if="exploring" class="marker-exploring-ring" r="3.1" />
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
    <!-- Cleared badge: small shield-check pinned to the marker's top-right -->
    <g v-if="cleared" class="marker-cleared-badge" aria-hidden="true">
      <circle cx="2.7" cy="-2.7" r="1.6" class="marker-cleared-badge-bg" />
      <path d="M 2.1 -3.3 L 2.6 -2.7 L 3.4 -3.7" class="marker-cleared-badge-check" />
    </g>
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

/* Non-interactive markers (free-roam explorer last-known positions) are
   click-through: no pointer cursor, no hover glow, no click capture. */
.marker-non-interactive {
  cursor: default;
  pointer-events: none;
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
  padding: 9%;
  box-sizing: border-box;
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
  opacity: 0;
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

/* Cleared points: dimmed marker + shield-check badge in the top-right corner */
.marker-cleared {
  opacity: 0.45;
}

.marker-cleared-badge-bg {
  fill: var(--color-surface);
  stroke: var(--color-theme-primary);
  stroke-width: 0.3;
}

.marker-cleared-badge-check {
  fill: none;
  stroke: var(--color-theme-primary);
  stroke-width: 0.45;
  stroke-linecap: round;
  stroke-linejoin: round;
}

/* Explorer tracking: pulsing warning ring around a dispatched target */
.marker-exploring-ring {
  fill: none;
  stroke: var(--color-warning);
  stroke-width: 0.35;
  opacity: 0.8;
  pointer-events: none;
  transform-box: fill-box;
  transform-origin: center;
  animation: exploring-pulse 1.6s ease-in-out infinite;
}

/* Free-roam explorer last-known position: accent-tinted, non-interactive */
.marker-explorer .marker-icon {
  color: var(--color-theme-accent);
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
    transform: scale(1.5);
  }
}

@keyframes exploring-pulse {
  0%,
  100% {
    opacity: 0.15;
    transform: scale(0.85);
  }
  50% {
    opacity: 0.9;
    transform: scale(1.25);
  }
}

@media (prefers-reduced-motion: reduce) {
  .marker-discovery,
  .marker-select-ping,
  .marker-exploring-ring {
    animation: none;
  }
}
</style>
