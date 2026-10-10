<script setup lang="ts">
import { computed, ref, useId, watch, type CSSProperties } from 'vue'
import { Icon } from '@iconify/vue'
import { getStaticImageUrl, normalizeImageUrl } from '@/core/utils/image'
import { markerTypeMeta, type MarkerType } from '../models/markerTypeMeta'
import { isHintLocation } from '../utils/visibility'

interface Props {
  x: number
  y: number
  name: string
  type: MarkerType
  selected?: boolean
  is_unlocked?: boolean
  unseen?: boolean
  icon?: string
  artSrc?: string | null
  color?: string | null
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
  color: null,
  cleared: false,
  exploring: false,
  interactive: true,
})

const emit = defineEmits<{
  (e: 'click', event: Event): void
}>()

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    emit('click', event)
  }
}

function handleClick(event: MouseEvent) {
  if (props.interactive) emit('click', event)
}

const meta = computed(() => markerTypeMeta(props.type))
const icon = computed(() => props.icon ?? meta.value.icon)
const label = computed(() => props.label ?? meta.value.label)
const isDiscovery = computed(() => props.type === 'discovery')
const isVault = computed(() => props.type === 'vault')

const isLocked = computed(() => isHintLocation(props))
const displayIcon = computed(() => (isLocked.value ? 'mdi:lock-question' : icon.value))
const displayLabel = computed(() => (isLocked.value ? 'Unknown Location' : props.name))
const shouldPulse = computed(() => isDiscovery.value && !isLocked.value && props.unseen)

// Glyph size in marker user units; the backing disc is r=3.8, so this leaves a
// ring of dark margin around every glyph. Passed to Iconify with an explicit
// unit: a unitless nested-<svg> width is rejected by Chromium (it then
// shrink-wraps each icon to its artwork) but honoured by Firefox.
const GLYPH_SIZE = 5.4
const GLYPH_SIZE_CSS = `${GLYPH_SIZE}px`
const portraitClipId = useId()

// Explorer thumbnail: normalise the backend static path and fall back to the
// icon glyph if the image fails to load (restores DwellerPortrait's behaviour
// after moving the glyph off <foreignObject>).
const portraitUrl = computed(() =>
  props.artSrc ? getStaticImageUrl(normalizeImageUrl(props.artSrc)) : null
)
const portraitFailed = ref(false)
watch(portraitUrl, () => {
  portraitFailed.value = false
})
const showPortrait = computed(
  () => Boolean(portraitUrl.value) && !isLocked.value && !portraitFailed.value
)

// Colour by state, or by place group when a `color` is passed in. Applied as an
// inline CSS colour on the glyph <g> (SVG inherits currentColor), so there is no
// <foreignObject> and no per-state colour CSS to keep in sync.
const glyphStyle = computed<CSSProperties>(() => {
  if (isLocked.value) return { color: 'var(--color-gray-400)', opacity: 0.8 }
  if (isVault.value) return { color: 'var(--color-warning)', opacity: 0.7 }
  if (props.type === 'explorer') return { color: 'var(--color-theme-accent)' }
  return { color: props.color ?? 'var(--color-theme-primary)' }
})

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
    <circle class="marker-hit-area" r="6" fill="transparent" />
    <title>{{ tooltipText }}</title>
    <!-- Dark knockout disc: keeps the glyph and rings legible over any terrain -->
    <circle class="marker-backing" r="3.8" />
    <circle v-if="selected" class="marker-select-ring" r="3.1" />
    <circle v-if="selected" class="marker-select-ping" r="3.1" />
    <circle v-if="exploring" class="marker-exploring-ring" r="3.1" />

    <!-- Glyph, rendered natively in SVG (no <foreignObject>) so it lands the same
         in every engine. Dweller thumbnails use <image> + a circular clip. -->
    <template v-if="showPortrait">
      <defs>
        <clipPath :id="portraitClipId">
          <circle r="3.1" />
        </clipPath>
      </defs>
      <image
        :href="portraitUrl ?? undefined"
        x="-3.1"
        y="-3.1"
        width="6.2"
        height="6.2"
        :clip-path="`url(#${portraitClipId})`"
        preserveAspectRatio="xMidYMin slice"
        @error="portraitFailed = true"
      />
    </template>
    <g
      v-else
      class="marker-glyph"
      :class="{ 'marker-discovery': shouldPulse }"
      :style="glyphStyle"
      :transform="`translate(${-GLYPH_SIZE / 2}, ${-GLYPH_SIZE / 2})`"
    >
      <Icon :icon="displayIcon" :width="GLYPH_SIZE_CSS" :height="GLYPH_SIZE_CSS" />
    </g>

    <!-- Cleared badge: small shield-check pinned to the marker's top-right -->
    <g v-if="cleared" class="marker-cleared-badge" aria-hidden="true">
      <circle cx="2.7" cy="-2.7" r="1.6" class="marker-cleared-badge-bg" />
      <path d="M 2.05 -2.7 L 2.5 -2.25 L 3.35 -3.15" class="marker-cleared-badge-check" />
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

/* Hover/focus emphasis is an SVG ring on the backing disc. */
.map-marker:hover .marker-backing,
.map-marker:focus-visible .marker-backing {
  stroke: var(--color-theme-primary);
  stroke-width: 0.35;
}

.map-marker:focus,
.map-marker:focus-visible {
  outline: none;
}

/* Uniform dark backing behind every glyph and ring. Slightly wider than the
   glyph, and near-opaque, so markers separate from light terrain. */
.marker-backing {
  fill: color-mix(in srgb, var(--color-terminal-background) 90%, transparent);
  pointer-events: none;
}

.marker-glyph {
  pointer-events: none;
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
.map-marker.marker-selected .marker-label {
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
  }
  50% {
    opacity: 1;
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
