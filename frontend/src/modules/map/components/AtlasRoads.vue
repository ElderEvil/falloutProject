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

// One isolated opacity group for the whole road network: SVG flattens the
// children first, unions their fully opaque strokes, then applies this once.
// That keeps shared endpoints and crossings from stacking alpha.
const ROAD_OPACITY = 0.72

// Survey graticule: every 16 units across the 160-unit viewBox (11 lines each way).
const GRATICULE_STEPS = Array.from({ length: 11 }, (_, index) => index * 16)

const REGION_NAMES = [
  'THE DIVIDE',
  'ASH FLATS',
  'RUST BELT',
  'GLOWING SEA',
  'DRY GULCH',
  'OLD TERRITORIES',
  'CINDER WASTES',
  'THE LONG 80',
] as const

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

interface RouteShield {
  id: string
  route: string
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

function midpointShield(segment: RoadSegment): RouteShield | null {
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
    route: routeNumber(segment.id),
    x: (x1 + x2) / 2,
    y: (y1 + y2) / 2,
    angle,
  }
}

const routeShields = computed<RouteShield[]>(() => {
  if (!detailed.value) return []
  const highway = layers.value.find((layer) => layer.kind === 'highway')
  return (highway?.segments ?? []).flatMap((segment) => {
    const shield = midpointShield(segment)
    return shield ? [shield] : []
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

interface RegionLabel {
  name: string
  x: number
  y: number
}

/**
 * Deterministic region stencils: one per 2x2 snapshot quadrant that carries
 * enough wasteland/ruins cells. Uses the same cheap hash as `conditionFor`
 * so the same snapshot always yields the same names.
 */
function checksumOffset(checksum: string): number {
  let hash = 0
  for (const char of checksum) hash = (hash * 31 + char.charCodeAt(0)) % 1009
  return hash
}

const regionLabels = computed<RegionLabel[]>(() => {
  const snapshot = props.snapshot
  if (!snapshot || overview.value) return []
  const { width, height, terrain } = snapshot
  if (width < 1 || height < 1 || terrain.length !== width * height) return []

  const offset = checksumOffset(snapshot.snapshot_checksum) % REGION_NAMES.length
  const halfWidth = Math.ceil(width / 2)
  const halfHeight = Math.ceil(height / 2)
  const labels: RegionLabel[] = []

  for (let quadrantY = 0; quadrantY < 2; quadrantY++) {
    for (let quadrantX = 0; quadrantX < 2; quadrantX++) {
      const x0 = quadrantX * halfWidth
      const y0 = quadrantY * halfHeight
      const x1 = Math.min(width, x0 + halfWidth)
      const y1 = Math.min(height, y0 + halfHeight)
      let count = 0
      let sumX = 0
      let sumY = 0
      for (let y = y0; y < y1; y++) {
        for (let x = x0; x < x1; x++) {
          const tile = terrain[y * width + x]
          if (tile !== 'wasteland' && tile !== 'ruins') continue
          count++
          sumX += x
          sumY += y
        }
      }
      const area = (x1 - x0) * (y1 - y0)
      if (count < Math.max(1, Math.floor(area * 0.02))) continue
      const quadrantIndex = quadrantY * 2 + quadrantX
      labels.push({
        name: REGION_NAMES[(quadrantIndex + offset) % REGION_NAMES.length],
        x: ((sumX / count + 0.5) / width) * MAP_UNITS,
        y: ((sumY / count + 0.5) / height) * MAP_UNITS,
      })
    }
  }
  return labels
})

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
      <g v-bind="{ 'data-role': 'graticule' }" :opacity="0.07" class="stroke-terrain-road">
        <line
          v-for="step in GRATICULE_STEPS"
          :key="`graticule-v-${step}`"
          :x1="step"
          y1="0"
          :x2="step"
          y2="160"
          stroke-width="0.12"
        />
        <line
          v-for="step in GRATICULE_STEPS"
          :key="`graticule-h-${step}`"
          x1="0"
          :y1="step"
          x2="160"
          :y2="step"
          stroke-width="0.12"
        />
      </g>

      <g
        v-if="!overview"
        v-bind="{ 'data-role': 'region-labels' }"
        :opacity="0.1"
        class="fill-terrain-road font-mono"
      >
        <text
          v-for="region in regionLabels"
          :key="`region-${region.name}`"
          :x="region.x"
          :y="region.y"
          font-size="6.2"
          letter-spacing="0.8"
          text-anchor="middle"
          dominant-baseline="middle"
          v-bind="{ 'data-role': 'region-label', 'data-region': region.name }"
        >
          {{ region.name }}
        </text>
      </g>

      <g v-bind="{ 'data-role': 'road-paint' }" :opacity="ROAD_OPACITY">
        <g v-for="layer in visibleLayers" :key="layer.kind" v-bind="{ 'data-layer': layer.kind }">
          <polyline
            v-for="road in layer.segments"
            :key="`${road.id}-casing`"
            :points="road.points"
            class="stroke-terminal-background"
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
              class="stroke-terrain-rail"
            />
          </template>
          <polyline
            v-for="road in layer.segments"
            :key="road.id"
            :points="road.points"
            :class="
              layer.kind === 'railroad'
                ? 'stroke-terrain-rail'
                : layer.kind === 'highway'
                  ? 'stroke-terrain-road'
                  : 'stroke-terrain-road-dim'
            "
            :stroke-width="layer.kind === 'railroad' ? 0.24 : layer.kind === 'highway' ? 0.8 : 0.36"
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
              class="stroke-terminal-background"
              v-bind="{ 'data-role': 'road-decay' }"
            />
          </template>
        </g>
      </g>

      <g v-if="detailed" v-bind="{ 'data-role': 'route-shields' }" :opacity="0.8">
        <g
          v-for="shield in routeShields"
          :key="`shield-${shield.id}`"
          :transform="`translate(${shield.x} ${shield.y}) rotate(${shield.angle})`"
          v-bind="{ 'data-role': 'route-shield', 'data-route': shield.route }"
        >
          <path
            d="M -2.2 -2 H 2.2 L 2.2 0.4 Q 2.2 2.4 0 2.8 Q -2.2 2.4 -2.2 0.4 Z"
            stroke-width="0.22"
            stroke-linejoin="round"
            class="fill-terminal-background stroke-terrain-road"
          />
          <text
            x="0"
            y="-1.25"
            font-size="0.8"
            letter-spacing="0.15"
            text-anchor="middle"
            dominant-baseline="middle"
            class="fill-terrain-road font-mono"
          >
            OLD
          </text>
          <text
            x="0"
            y="0.2"
            font-size="1.9"
            letter-spacing="0.1"
            text-anchor="middle"
            dominant-baseline="middle"
            class="fill-terrain-road font-mono"
          >
            {{ shield.route }}
          </text>
        </g>
      </g>

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
