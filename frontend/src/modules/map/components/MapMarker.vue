<script setup lang="ts">
import { computed, ref, useId, watch, type CSSProperties } from 'vue'
import { Icon } from '@iconify/vue'
import { getStaticImageUrl, normalizeImageUrl } from '@/core/utils/image'
import { MARKER_GLYPH_SIZE, markerTypeMeta, type MarkerType } from '../models/markerTypeMeta'
import { purposeMeta, type PlacePurpose } from '../models/purposeMeta'
import { riskLabel } from '../utils/dangerStyle'
import { isHintLocation } from '../utils/visibility'

interface Props {
  x: number
  y: number
  name: string
  type: MarkerType
  /** What the place is for; drives the body shape. Null keeps the plain disc. */
  purpose?: PlacePurpose | null
  selected?: boolean
  is_unlocked?: boolean
  unseen?: boolean
  icon?: string
  artSrc?: string | null
  color?: string | null
  label?: string
  cooldown?: boolean
  cleared?: boolean
  exploring?: boolean
  status?: string
  risk?: string | null
  baseDifficulty?: number | null
  interactive?: boolean
  scale?: number
  /** Glyph-only scale; the backing disc and hit area stay full size. */
  iconScale?: number
  /**
   * Body scale: shrinks the disc, rings, badges, portrait and label together.
   * The glyph keeps its own size (see `iconScale`) and the hit area stays full,
   * so a smaller marker reads tighter without becoming harder to click.
   */
  bodyScale?: number
}

const props = withDefaults(defineProps<Props>(), {
  color: null,
  purpose: null,
  selected: false,
  is_unlocked: true,
  unseen: false,
  cooldown: false,
  cleared: false,
  exploring: false,
  interactive: true,
  scale: 1,
  iconScale: 1,
  bodyScale: 1,
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
// Identity is the place's archetype, never its discovery state: an unscouted
// pin shows the same glyph dimmed inside a dashed ring, so the map never spends
// a marker on a "?" glyph that says nothing about the place.
const displayIcon = computed(() => icon.value)
const displayLabel = computed(() => (isLocked.value ? 'Unknown Location' : props.name))
const shouldPulse = computed(() => isDiscovery.value && !isLocked.value && props.unseen)

// Glyph size in marker user units; the backing disc is r=3.8, so this leaves a
// ring of dark margin around every glyph. Passed to Iconify with an explicit
// unit: a unitless nested-<svg> width is rejected by Chromium (it then
// shrink-wraps each icon to its artwork) but honoured by Firefox.
const glyphSize = computed(() => MARKER_GLYPH_SIZE * props.iconScale)
const glyphSizeCss = computed(() => `${glyphSize.value}px`)

// Every body dimension derives from one factor so disc, rings, badge, portrait
// and label shrink as a single unit instead of drifting out of proportion.
// Rounded to three decimals: float noise in an SVG radius attr is just noise.
const body = (value: number): number => Math.round(value * props.bodyScale * 1000) / 1000
const discRadius = computed(() => body(4.2))
const ringRadius = computed(() => body(3.1))
const portraitSize = computed(() => body(6.2))
const labelY = computed(() => -body(3.4))
const labelStyle = computed<CSSProperties>(() => ({ fontSize: `${body(2.4)}px` }))
const portraitClipId = useId()

// Body shape carries purpose: circle = clear, diamond = trade, open ring = look,
// square = your vault. A marker without a purpose keeps the plain disc, so
// signals and parties read exactly as they always have.
const purposeShape = computed(() => (props.purpose ? purposeMeta(props.purpose).shape : 'circle'))
const purposeLabel = computed(() => (props.purpose ? purposeMeta(props.purpose).label : null))
const diamondPath = computed(() => {
  const r = discRadius.value
  return `M 0 ${-r} L ${r} 0 L 0 ${r} L ${-r} 0 Z`
})

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

const glyphStyle = computed<CSSProperties>(() => ({
  color: !isLocked.value && props.color ? props.color : 'var(--color-theme-primary)',
}))

const tooltipText = computed(() => {
  const base = `${displayLabel.value} (${label.value})`
  const details = [
    purposeLabel.value,
    isLocked.value ? null : riskLabel(props.risk, props.baseDifficulty),
    props.cooldown ? 'Cooldown' : props.cleared ? 'Cleared' : null,
    props.status,
  ].filter(Boolean)
  return details.length ? `${base} — ${details.join(' · ')}` : base
})
</script>

<template>
  <g
    :transform="`translate(${x}, ${y})${scale === 1 ? '' : ` scale(${scale})`}`"
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
    <!-- Dark knockout body: keeps the glyph and rings legible over any terrain.
         Its shape encodes purpose — circle clear, diamond trade, open ring look,
         square home — while signals keep the plain disc. -->
    <circle v-if="purposeShape === 'circle'" class="marker-backing" :r="discRadius" />
    <path v-else-if="purposeShape === 'diamond'" class="marker-backing" :d="diamondPath" />
    <circle
      v-else-if="purposeShape === 'ring'"
      class="marker-backing marker-backing-open"
      :r="discRadius"
    />
    <rect
      v-else
      class="marker-backing"
      :x="-discRadius"
      :y="-discRadius"
      :width="discRadius * 2"
      :height="discRadius * 2"
      :rx="discRadius * 0.32"
    />
    <circle v-if="selected" class="marker-select-ring" :r="ringRadius" />
    <circle v-if="selected" class="marker-select-ping" :r="ringRadius" />
    <circle v-if="exploring" class="marker-exploring-ring" :r="ringRadius" />

    <!-- Glyph, rendered natively in SVG (no <foreignObject>) so it lands the same
         in every engine. Dweller thumbnails use <image> + a circular clip. -->
    <template v-if="showPortrait">
      <defs>
        <clipPath :id="portraitClipId">
          <circle :r="ringRadius" />
        </clipPath>
      </defs>
      <image
        :href="portraitUrl ?? undefined"
        :x="-portraitSize / 2"
        :y="-portraitSize / 2"
        :width="portraitSize"
        :height="portraitSize"
        :clip-path="`url(#${portraitClipId})`"
        preserveAspectRatio="xMidYMin slice"
        @error="portraitFailed = true"
      />
    </template>
    <g
      v-else
      class="marker-glyph"
      :style="glyphStyle"
      :class="{ 'marker-discovery': shouldPulse, 'opacity-50': isLocked }"
      :transform="`translate(${-glyphSize / 2}, ${-glyphSize / 2})`"
    >
      <Icon :icon="displayIcon" :width="glyphSizeCss" :height="glyphSizeCss" />
    </g>

    <!-- Cleared badge: small shield-check pinned to the marker's top-right -->
    <g
      v-if="!isLocked && (cleared || cooldown)"
      :class="cooldown ? 'marker-cooldown-badge' : 'marker-cleared-badge'"
      :transform="`scale(${bodyScale})`"
      aria-hidden="true"
    >
      <circle cx="2.7" cy="-2.7" r="1.6" class="marker-cleared-badge-bg" />
      <path
        :d="cooldown ? 'M 2.7 -3.65 V -2.7 L 3.35 -2.25' : 'M 2.05 -2.7 L 2.5 -2.25 L 3.35 -3.15'"
        class="marker-cleared-badge-check"
      />
    </g>
    <!-- Label: hidden by default, shown on hover/focus/selected via CSS -->
    <text
      class="marker-label"
      x="0"
      :y="labelY"
      :style="labelStyle"
      text-anchor="middle"
      aria-hidden="true"
      >{{ displayLabel }}</text
    >
  </g>
</template>

<style scoped>
.map-marker {
  --marker-accent: var(--color-theme-primary);
  --marker-glow: 0.7px;

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

/* Unscouted places keep their archetype glyph but wear a dashed ring, so the
   state still reads at a glance without spending the marker on a "?" glyph. */
.marker-locked .marker-backing {
  stroke-dasharray: 0.9 0.7;
  opacity: 0.75;
}

.map-marker:focus,
.map-marker:focus-visible {
  outline: none;
}

/* Uniform dark backing behind every glyph and ring. Slightly wider than the
   glyph, and near-opaque, so markers separate from light terrain. */
.marker-backing {
  fill: color-mix(in srgb, var(--color-terminal-background) 90%, transparent);
  stroke: var(--marker-accent);
  stroke-width: 0.35;
  filter: drop-shadow(0 0 var(--marker-glow) var(--marker-accent));
  pointer-events: none;
}

.marker-glyph {
  pointer-events: none;
}

/* Look places (landmarks, regions) are open bodies: you read them, you do not raid them. */
.marker-backing-open {
  fill: none;
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
  stroke: var(--color-theme-primary);
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
