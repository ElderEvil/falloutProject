<script setup lang="ts">
import { computed, useId } from 'vue'
import type { WorldSnapshotRead } from '../models/map'
import { MAP_UNITS, registryToWire } from '../utils/atlasProjection'

const props = defineProps<{
  snapshot: WorldSnapshotRead | null
  explored: Uint8Array
  fogDisabled?: boolean
}>()

const clipId = `roads-explored-${useId()}`
const layers = computed(() => {
  const snapshot = props.snapshot
  const roads = snapshot?.roads
  if (!roads || roads.base_checksum !== snapshot?.snapshot_checksum) return []
  return (['railroad', 'country', 'highway'] as const).map((kind) => ({
    kind,
    segments: roads.segments
      .filter((road) => road.kind === kind)
      .map((road) => ({
        id: road.id,
        // Geometry (including rounding) is backend-owned. No client smoothing.
        points: road.points.map(([x, y]) => `${registryToWire(x)},${registryToWire(y)}`).join(' '),
      })),
  }))
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
      <g v-for="layer in layers" :key="layer.kind" v-bind="{ 'data-layer': layer.kind }">
        <polyline
          v-for="road in layer.segments"
          :key="`${road.id}-casing`"
          :points="road.points"
          class="stroke-terminal-background/70"
          :stroke-width="layer.kind === 'country' ? 0.68 : 1.36"
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
        />
      </g>
    </g>
  </g>
</template>
