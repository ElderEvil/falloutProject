<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { useMapStore } from '../stores/map'
import {
  ATLAS_TERRAIN_ORDER,
  ATLAS_TERRAIN_VAR,
  MAP_UNITS,
} from '../utils/atlasProjection'
import type { TerrainType } from '../utils/atlasWorldgen'

const store = useMapStore()
const imageUrl = ref('')

// Backend-owned terrain: renders the persisted snapshot verbatim. No local
// generation, no fallback geography — a missing snapshot renders nothing rather
// than a second, divergent world. Roads are omitted deliberately: the snapshot
// carries no roads, and unrelated TS roads must not masquerade as movement
// authority (travel stays distance-based until approved).
function resolveTerrainColors(): Record<TerrainType, string> {
  const styles = getComputedStyle(document.documentElement)
  const colors = {} as Record<TerrainType, string>
  for (const terrain of ATLAS_TERRAIN_ORDER) {
    colors[terrain] = styles.getPropertyValue(ATLAS_TERRAIN_VAR[terrain]).trim() || '#000000'
  }
  return colors
}

function renderTerrain(): void {
  const snapshot = store.worldSnapshot
  if (snapshot === null) {
    imageUrl.value = ''
    return
  }
  const { width, height } = snapshot
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d')
  if (ctx === null) {
    imageUrl.value = ''
    return
  }
  const colors = resolveTerrainColors()
  for (let i = 0; i < snapshot.terrain.length; i++) {
    ctx.fillStyle = colors[snapshot.terrain[i] as TerrainType] ?? '#000000'
    ctx.fillRect(i % width, Math.floor(i / width), 1, 1)
  }
  imageUrl.value = canvas.toDataURL()
}

watch(() => store.worldSnapshot, renderTerrain, { immediate: true })
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
  </g>
</template>

<style scoped>
.atlas-terrain {
  opacity: 1;
}

.atlas-image {
  image-rendering: pixelated;
}
</style>
