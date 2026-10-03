<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useMapStore } from '../stores/map'
import {
  ATLAS_SEED,
  ATLAS_TILES,
  ATLAS_TERRAIN_ORDER,
  ATLAS_TERRAIN_VAR,
  MAP_UNITS,
  anchorsFromVaultMarkers,
} from '../utils/atlasProjection'
import { generateWorld, type TerrainType } from '../utils/atlasWorldgen'

const store = useMapStore()
const imageUrl = ref('')

// One shared seeded world, anchored to the global seeded vault signals only. It
// deliberately does NOT consume player-vault anchors: geography must stay stable
// as vault occupancy changes, so player vaults are placement markers on the fixed
// world, never terrain shapers.
const world = computed(() =>
  generateWorld(
    { seed: ATLAS_SEED, width: ATLAS_TILES, height: ATLAS_TILES },
    anchorsFromVaultMarkers(store.vaultMarkers),
  ),
)

const roadPaths = computed(() => {
  const w = world.value
  const unitX = MAP_UNITS / w.config.width
  const unitY = MAP_UNITS / w.config.height
  return w.roads.map(edge =>
    edge.path
      .map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x * unitX} ${p.y * unitY}`)
      .join(' '),
  )
})

function resolveTerrainColors(): Record<TerrainType, string> {
  const styles = getComputedStyle(document.documentElement)
  const colors = {} as Record<TerrainType, string>
  for (const terrain of ATLAS_TERRAIN_ORDER) {
    colors[terrain] = styles.getPropertyValue(ATLAS_TERRAIN_VAR[terrain]).trim() || '#000000'
  }
  return colors
}

function renderTerrain(): void {
  const w = world.value
  const { width, height } = w.config
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d')
  if (ctx === null) {
    imageUrl.value = ''
    return
  }
  const colors = resolveTerrainColors()
  for (let i = 0; i < w.terrain.length; i++) {
    ctx.fillStyle = colors[w.terrain[i]]
    ctx.fillRect(i % width, Math.floor(i / width), 1, 1)
  }
  imageUrl.value = canvas.toDataURL()
}

watch(world, renderTerrain, { immediate: true })
onBeforeUnmount(() => {
  imageUrl.value = ''
})
</script>

<template>
  <g class="atlas-terrain" aria-hidden="true">
    <image
      v-if="imageUrl"
      :href="imageUrl"
      x="0"
      y="0"
      :width="MAP_UNITS"
      :height="MAP_UNITS"
      preserveAspectRatio="none"
      class="atlas-image"
    />
    <path
      v-for="(d, i) in roadPaths"
      :key="`atlas-road-casing-${i}`"
      :d="d"
      class="atlas-road-casing"
      fill="none"
    />
    <path
      v-for="(d, i) in roadPaths"
      :key="`atlas-road-${i}`"
      :d="d"
      class="atlas-road"
      fill="none"
    />
  </g>
</template>

<style scoped>
.atlas-terrain {
  opacity: 1;
}

.atlas-image {
  image-rendering: pixelated;
}

.atlas-road-casing {
  stroke: rgba(0, 0, 0, 0.55);
  stroke-width: 1.1;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.atlas-road {
  stroke: var(--color-terrain-road);
  stroke-width: 0.5;
  stroke-linecap: round;
  stroke-linejoin: round;
  opacity: 0.95;
}
</style>
