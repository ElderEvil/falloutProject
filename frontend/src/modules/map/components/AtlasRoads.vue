<script setup lang="ts">
import { computed, useId } from 'vue'
import type { WorldSnapshotRead } from '../models/map'
import { MAP_UNITS, registryToWire } from '../utils/atlasProjection'

const props = defineProps<{
  snapshot: WorldSnapshotRead | null
  explored: Uint8Array
  fogDisabled?: boolean
  /** Current map zoom; 1 is the full-world overview, 5 is the closest view. */
  zoom?: number
}>()

// Overview keeps only the long-distance network; close zoom reveals the
// pre-war detail (dashes, decay, labels, rail stops). Both are decoration over
// backend-owned geometry.
const OVERVIEW_ZOOM = 2
const DETAIL_ZOOM = 4

const zoom = computed(() => props.zoom ?? 1)
const overview = computed(() => zoom.value < OVERVIEW_ZOOM)
const detailed = computed(() => zoom.value >= DETAIL_ZOOM)

const clipId = `roads-explored-${useId()}`

interface RoadSegment {
  id: string
  condition: number
  points: string
}

interface RoadLayer {
  kind: 'railroad' | 'country' | 'highway'
  segments: RoadSegment[]
}

/** Deterministic per-segment wear, so the same snapshot always looks the same. */
function conditionFor(id: string): number {
  let hash = 0
  for (const char of id) hash = (hash * 31 + char.charCodeAt(0)) % 1009
  return 0.35 + (hash % 61) / 100
}

const layers = computed<RoadLayer[]>(() => {
  const snapshot = props.snapshot
  const roads = snapshot?.roads
  if (!roads || roads.base_checksum !== snapshot?.snapshot_checksum) return []
  return (['railroad', 'country', 'highway'] as const).map((kind) => ({
    kind,
    segments: roads.segments
      .filter((road) => road.kind === kind)
      .map((road) => ({
        id: road.id,
        condition: conditionFor(road.id),
        // Geometry (including rounding) is backend-owned. No client smoothing.
        points: road.points.map(([x, y]) => `${registryToWire(x)},${registryToWire(y)}`).join(' '),
      })),
  }))
})

const visibleLayers = computed(() =>
  overview.value ? layers.value.filter((layer) => layer.kind !== 'country') : layers.value
)

interface Junction {
  key: string
  x: number
  y: number
}

/** Vertices shared by two or more road segments, so intersections read as junctions. */
const junctions = computed<Junction[]>(() => {
  if (overview.value) return []
  const seen = new Map<string, { x: number; y: number; count: number }>()
  for (const layer of layers.value) {
    if (layer.kind === 'railroad') continue
    for (const segment of layer.segments) {
      for (const point of new Set(segment.points.split(' '))) {
        const [x, y] = point.split(',').map(Number)
        const entry = seen.get(point) ?? { x, y, count: 0 }
        entry.count += 1
        seen.set(point, entry)
      }
    }
  }
  return [...seen.entries()]
    .filter(([, entry]) => entry.count > 1)
    .map(([key, entry]) => ({ key, x: entry.x, y: entry.y }))
})

interface RoadLabel {
  id: string
  text: string
  x: number
  y: number
  angle: number
}

/** Fictional pre-war route number derived from the segment id. */
function routeNumber(id: string): string {
  let hash = 0
  for (const char of id) hash = (hash * 33 + char.charCodeAt(0)) % 89
  return String(10 + hash)
}

function midpointLabel(segment: RoadSegment): RoadLabel | null {
  const coords = segment.points.split(' ').map((point) => point.split(',').map(Number))
  if (coords.length < 2) return null
  const index = Math.floor((coords.length - 1) / 2)
  const [x1, y1] = coords[index]
  const [x2, y2] = coords[index + 1]
  let angle = (Math.atan2(y2 - y1, x2 - x1) * 180) / Math.PI
  if (angle > 90) angle -= 180
  if (angle < -90) angle += 180
  return {
    id: segment.id,
    text: `OLD ${routeNumber(segment.id)}`,
    x: (x1 + x2) / 2,
    y: (y1 + y2) / 2 - 0.9,
    angle,
  }
}

const roadLabels = computed<RoadLabel[]>(() => {
  if (!detailed.value) return []
  const highway = layers.value.find((layer) => layer.kind === 'highway')
  return (highway?.segments ?? []).flatMap((segment) => {
    const label = midpointLabel(segment)
    return label ? [label] : []
  })
})

interface RailStop {
  key: string
  kind: 'station' | 'water-tower'
  x: number
  y: number
}

const railStops = computed<RailStop[]>(() => {
  if (!detailed.value) return []
  const railroad = layers.value.find((layer) => layer.kind === 'railroad')
  return (railroad?.segments ?? []).flatMap((segment) => {
    const points = segment.points.split(' ')
    const stop = (kind: RailStop['kind'], key: string, point: string): RailStop => {
      const [x, y] = point.split(',').map(Number)
      return { key, kind, x, y }
    }
    return [
      stop('station', `${segment.id}-start`, points[0]),
      stop('water-tower', `${segment.id}-end`, points[points.length - 1]),
    ]
  })
})

/** Worn roads fade with distance at close zoom; overview keeps full contrast. */
function roadOpacity(condition: number): number {
  return detailed.value ? 0.55 + 0.45 * condition : 1
}

// One SVG path of explored horizontal runs, rather than thousands of tile nodes.
// An absent/mismatched mask reveals nothing. This also clips the road casings.
const exploredClip = computed(() => {
  const snapshot = props.snapshot
  if (!snapshot || props.explored.length !== snapshot.width * snapshot.height) return ''
  const { width, height } = snapshot
  const sx = MAP_UNITS / width
  const sy = MAP_UNITS / height
  const runs: string[] = []
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      if (props.explored[y * width + x] !== 1) continue
      const start = x
      while (x + 1 < width && props.explored[y * width + x + 1] === 1) x++
      runs.push(`M${start * sx} ${y * sy}h${(x - start + 1) * sx}v${sy}H${start * sx}Z`)
    }
  }
  return runs.join(' ')
})
</script>

<template>
  <g v-if="layers.length" class="atlas-roads pointer-events-none" aria-hidden="true">
    <defs>
      <clipPath :id="clipId" clipPathUnits="userSpaceOnUse">
        <path :d="exploredClip" />
      </clipPath>
    </defs>
    <g
      :clip-path="fogDisabled ? undefined : `url(#${clipId})`"
      fill="none"
      stroke-linecap="round"
      stroke-linejoin="round"
    >
      <g v-for="layer in visibleLayers" :key="layer.kind" v-bind="{ 'data-layer': layer.kind }">
        <polyline
          v-for="road in layer.segments"
          :key="`${road.id}-casing`"
          :points="road.points"
          class="stroke-terminal-background/70"
          :stroke-width="layer.kind === 'country' ? 0.68 : 1.36"
          v-bind="{ 'data-role': 'casing' }"
        />
        <template v-if="layer.kind === 'railroad'">
          <polyline
            v-for="road in layer.segments"
            :key="`${road.id}-sleepers`"
            :points="road.points"
            stroke-linecap="butt"
            stroke-width="1.1"
            stroke-dasharray="0.14 0.8"
            class="stroke-terrain-rail/70"
          />
        </template>
        <polyline
          v-for="road in layer.segments"
          :key="road.id"
          :points="road.points"
          :class="
            layer.kind === 'railroad'
              ? 'stroke-terrain-rail/90'
              : layer.kind === 'highway'
                ? 'stroke-terrain-road/85'
                : 'stroke-terrain-road/60'
          "
          :stroke-width="layer.kind === 'railroad' ? 0.24 : layer.kind === 'highway' ? 0.8 : 0.36"
          :opacity="roadOpacity(road.condition)"
          v-bind="{ 'data-role': 'road' }"
        />
        <template v-if="layer.kind === 'highway' && !overview">
          <polyline
            v-for="road in layer.segments"
            :key="`${road.id}-dashes`"
            :points="road.points"
            stroke-width="0.14"
            stroke-linecap="butt"
            stroke-dasharray="0.7 0.9"
            class="stroke-terrain-road"
            opacity="0.85"
            v-bind="{ 'data-role': 'highway-dashes' }"
          />
        </template>
        <template v-if="detailed">
          <polyline
            v-for="road in layer.segments.filter((segment) => segment.condition < 0.5)"
            :key="`${road.id}-decay`"
            :points="road.points"
            :stroke-width="layer.kind === 'country' ? 0.18 : 0.32"
            stroke-dasharray="0.4 1.2"
            stroke-linecap="butt"
            class="stroke-terminal-background/60"
            v-bind="{ 'data-role': 'road-decay' }"
          />
        </template>
      </g>

      <circle
        v-for="junction in junctions"
        :key="`junction-${junction.key}`"
        :cx="junction.x"
        :cy="junction.y"
        r="0.55"
        stroke-width="0.18"
        class="fill-terminal-background stroke-terrain-road/80"
        v-bind="{ 'data-role': 'junction' }"
      />

      <text
        v-for="label in roadLabels"
        :key="`label-${label.id}`"
        :x="label.x"
        :y="label.y"
        :transform="`rotate(${label.angle} ${label.x} ${label.y})`"
        text-anchor="middle"
        dominant-baseline="middle"
        font-size="2.2"
        letter-spacing="0.25"
        fill="currentColor"
        class="font-mono text-terrain-road/60"
        v-bind="{ 'data-role': 'road-label' }"
      >
        {{ label.text }}
      </text>

      <g
        v-for="stop in railStops"
        :key="stop.key"
        :transform="`translate(${stop.x} ${stop.y})`"
        v-bind="{ 'data-role': 'rail-stop' }"
      >
        <template v-if="stop.kind === 'station'">
          <rect
            x="-1.6"
            y="-1.6"
            width="3.2"
            height="3.2"
            stroke-width="0.18"
            class="fill-terminal-background stroke-terrain-rail/80"
          />
        </template>
        <template v-else>
          <circle
            cx="0"
            cy="-2.2"
            r="1.1"
            stroke-width="0.18"
            class="fill-terminal-background stroke-terrain-rail/80"
          />
          <line
            x1="-0.8"
            y1="-1.1"
            x2="-0.8"
            y2="0.8"
            stroke-width="0.18"
            class="stroke-terrain-rail/80"
          />
          <line
            x1="0.8"
            y1="-1.1"
            x2="0.8"
            y2="0.8"
            stroke-width="0.18"
            class="stroke-terrain-rail/80"
          />
        </template>
      </g>
    </g>
  </g>
</template>
