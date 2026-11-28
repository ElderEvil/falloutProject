<script setup lang="ts">
import { computed, ref, useId, watch, type CSSProperties } from 'vue'
import { Icon } from '@iconify/vue'
import { getStaticImageUrl, normalizeImageUrl } from '@/core/utils/image'
import { MARKER_GLYPH_SIZE, markerTypeMeta, type MarkerType } from '../models/markerTypeMeta'
import { shapeMeta, type MarkerShape } from '../models/markerShape'
import { riskLabel } from '../utils/dangerStyle'
import { isHintLocation } from '../utils/visibility'

interface Props {
  x: number
  y: number
  name: string
  type: MarkerType
  /** Body silhouette the marker draws. Null keeps the plain disc. */
  shape?: MarkerShape | null
  selected?: boolean
  is_unlocked?: boolean
  unseen?: boolean
  icon?: string
  artSrc?: string | null
  color?: string | null
  label?: string
  archetype?: string
  cooldown?: boolean
  cleared?: boolean
  salvage?: boolean
  exploring?: boolean
  pulse?: boolean
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
  shape: null,
  selected: false,
  is_unlocked: true,
  unseen: false,
  cooldown: false,
  cleared: false,
  salvage: false,
  exploring: false,
  pulse: false,
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
const displayIcon = computed(() => (isLocked.value ? 'mdi:map-marker-question' : icon.value))
const displayLabel = computed(() => (isLocked.value ? 'Unknown Location' : props.name))
const shouldPulse = computed(
  () => props.pulse || (isDiscovery.value && !isLocked.value && props.unseen)
)

// Glyph size in marker user units. It follows the body scale, so the glyph keeps
// the same share of the body whether the marker is a full-size signal or a
// shrunk place marker — the old split left signal glyphs at 89% of their disc.
// Passed to Iconify with an explicit unit: a unitless nested-<svg> width is
// rejected by Chromium (it then shrink-wraps each icon to its artwork) but
// honoured by Firefox.
const glyphSize = computed(() => MARKER_GLYPH_SIZE * props.iconScale * props.bodyScale)
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

// An omitted shape keeps the plain disc for signals; an invalid one resolves to Look.
const bodyShape = computed<MarkerShape>(() =>
  props.shape ? shapeMeta(props.shape).shape : 'circle'
)
const purposeLabel = computed(() => (props.shape ? shapeMeta(props.shape).label : null))
const badgeKind = computed(() => {
  if (isLocked.value) return null
  if (props.cooldown) return 'cooldown'
  if (props.cleared) return 'cleared'
  return props.salvage ? 'salvage' : null
})
const bodyPath = computed(() => {
  const r = discRadius.value
  if (bodyShape.value === 'diamond') return `M 0 ${-r} L ${r} 0 L 0 ${r} L ${-r} 0 Z`
  if (bodyShape.value === 'hexagon') {
    // A hexagon holds ~83% of a disc's area at equal circumradius, so 1.1x brings
    // its footprint back to parity and it does not read as a small badge beside the
    // circles. Point-up, so the top vertex sits where the disc's edge did.
    const h = Math.round(r * 1.1 * 1000) / 1000
    const dx = Math.round(h * (Math.sqrt(3) / 2) * 1000) / 1000
    const dy = Math.round((h / 2) * 1000) / 1000
    return `M 0 ${-h} L ${dx} ${-dy} L ${dx} ${dy} L 0 ${h} L ${-dx} ${dy} L ${-dx} ${-dy} Z`
  }
  return ''
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
  const risk = isLocked.value ? null : riskLabel(props.risk, props.baseDifficulty)
  const states = [
    props.cooldown ? 'Cooldown' : props.cleared ? 'Cleared' : null,
    props.salvage ? 'Salvage available' : null,
    props.status,
  ].filter(Boolean)
  if (!props.shape) {
    const base = `${displayLabel.value} (${label.value})`
    const details = [risk, ...states].filter(Boolean)
    return details.length ? `${base} — ${details.join(' · ')}` : base
  }
  if (isLocked.value) return `Unscouted · ${purposeLabel.value} site · risk unknown`
  return [purposeLabel.value, props.archetype ?? displayLabel.value, risk, ...states]
    .filter(Boolean)
    .join(' · ')
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
         Its silhouette encodes purpose — circle clear, diamond trade, hollow square
         look, hexagon home — while signals keep the plain disc. -->
    <circle v-if="bodyShape === 'circle'" class="marker-backing" :r="discRadius" />
    <path
      v-else-if="bodyShape === 'diamond' || bodyShape === 'hexagon'"
      class="marker-backing"
      :d="bodyPath"
    />
    <rect
      v-else
      class="marker-backing marker-backing-open"
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

    <g
      v-if="badgeKind"
      :class="`marker-${badgeKind}-badge`"
      :transform="`scale(${bodyScale})`"
      aria-hidden="true"
    >
      <circle cx="2.7" cy="-2.7" r="1.6" class="marker-badge-bg" />
      <path
        v-if="badgeKind === 'cooldown'"
        d="M 2.7 -3.65 V -2.7 L 3.35 -2.25"
        class="marker-badge-mark"
      />
      <path
        v-else-if="badgeKind === 'cleared'"
        d="M 2.05 -2.7 L 2.5 -2.25 L 3.35 -3.15"
        class="marker-badge-mark"
      />
      <g v-else class="marker-badge-mark">
        <rect x="2.05" y="-3.35" width="1.3" height="1.3" rx="0.18" />
        <path d="M2.05 -2.9 H3.35" />
      </g>
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
  animation: select-ping 2.4s ease-out infinite;
}

.marker-cleared {
  opacity: 0.45;
}

.marker-badge-bg {
  fill: var(--color-surface);
  stroke: var(--color-theme-primary);
  stroke-width: 0.3;
}

.marker-badge-mark {
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
