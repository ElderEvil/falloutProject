<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { useMapStore } from '../stores/map'
import {
  ATLAS_TERRAIN_ORDER,
  ATLAS_TERRAIN_VAR,
  MAP_UNITS,
} from '../utils/atlasProjection'
import { maskToRects, type MaskRect } from '../utils/maskGeometry'
import type { TerrainType } from '../models/terrain'

const props = withDefaults(
  defineProps<{
    /** Display-only road mask: flat, sorted tile indices over the snapshot grid. */
    roads?: readonly number[]
    /** Display-only river mask: flat, sorted tile indices over the snapshot grid. */
    rivers?: readonly number[]
  }>(),
  { roads: () => [], rivers: () => [] },
)

const store = useMapStore()
const imageUrl = ref('')

// Backend-owned terrain: renders the persisted snapshot verbatim. No local
// generation, no fallback geography — a missing snapshot renders nothing rather
// than a second, divergent world. The snapshot's road and river masks are
// display-only tile lists painted over the biomes (cased roads, water-token
// rivers) and carry no movement authority.
//
// Terrain is categorical, so it is first painted 1px-per-cell, then bilinearly
// upscaled to blend differing biomes across their boundary, then given a
// deterministic per-pixel dither so flat regions do not band. Both steps are
// pure functions of the snapshot (no Math.random), so a given world renders
// identically every time. The masks paint on the upscaled canvas — before the
// dither — so they stay crisp instead of blending into the biome edges, and
// they live in the same texture, so the fog layer covers them unchanged.
const SUPERSAMPLE = 4
const DITHER_RANGE = 3
/** Fraction of a tile a mask rect bleeds outward, so diagonal steps connect. */
const MASK_BLEED = 0.25

const ROAD_FILL_VAR = '--color-terrain-road'
const ROAD_CASING_VAR = '--color-terrain-road-casing'
const RIVER_FILL_VAR = '--color-terrain-water'

/** Deterministic per-pixel brightness offset in [-DITHER_RANGE, DITHER_RANGE]. */
function ditherOffset(x: number, y: number): number {
  let h = (x * 374761393 + y * 668265263) | 0
  h = Math.imul(h ^ (h >>> 13), 1274126177)
  h ^= h >>> 16
  return ((h & 0xff) / 255 - 0.5) * 2 * DITHER_RANGE
}

function tokenColor(styles: CSSStyleDeclaration, name: string, fallback: string): string {
  return styles.getPropertyValue(name).trim() || fallback
}

function resolveTerrainColors(): Record<TerrainType, string> {
  const styles = getComputedStyle(document.documentElement)
  const colors = {} as Record<TerrainType, string>
  for (const terrain of ATLAS_TERRAIN_ORDER) {
    colors[terrain] = tokenColor(styles, ATLAS_TERRAIN_VAR[terrain], '#000000')
  }
  return colors
}

/**
 * Paint wire-space mask rects onto the upscaled canvas. `bleed` expands every
 * rect (in wire units) so orthogonally and diagonally adjacent tiles fuse into
 * one continuous ribbon instead of a dotted tile chain.
 */
function paintMaskRects(
  ctx: CanvasRenderingContext2D,
  rects: readonly MaskRect[],
  scale: number,
  color: string,
  bleed: number,
): void {
  ctx.fillStyle = color
  for (const rect of rects) {
    ctx.fillRect(
      (rect.x - bleed) * scale,
      (rect.y - bleed) * scale,
      (rect.width + bleed * 2) * scale,
      (rect.height + bleed * 2) * scale,
    )
  }
}

function renderTerrain(): void {
  const snapshot = store.worldSnapshot
  if (snapshot === null) {
    imageUrl.value = ''
    return
  }
  const { width, height } = snapshot
  const cells = document.createElement('canvas')
  cells.width = width
  cells.height = height
  const cellCtx = cells.getContext('2d')
  if (cellCtx === null) {
    imageUrl.value = ''
    return
  }
  const colors = resolveTerrainColors()
  for (let i = 0; i < snapshot.terrain.length; i++) {
    cellCtx.fillStyle = colors[snapshot.terrain[i] as TerrainType] ?? '#000000'
    cellCtx.fillRect(i % width, Math.floor(i / width), 1, 1)
  }

  const canvas = document.createElement('canvas')
  canvas.width = width * SUPERSAMPLE
  canvas.height = height * SUPERSAMPLE
  const ctx = canvas.getContext('2d')
  if (ctx === null) {
    imageUrl.value = ''
    return
  }
  ctx.imageSmoothingEnabled = true
  ctx.imageSmoothingQuality = 'high'
  ctx.drawImage(cells, 0, 0, canvas.width, canvas.height)

  const styles = getComputedStyle(document.documentElement)
  const scale = canvas.width / MAP_UNITS
  const bleed = (MAP_UNITS / width) * MASK_BLEED
  const riverRects = maskToRects(props.rivers, width)
  if (riverRects.length > 0) {
    paintMaskRects(ctx, riverRects, scale, tokenColor(styles, RIVER_FILL_VAR, '#253440'), bleed)
  }
  const roadRects = maskToRects(props.roads, width)
  if (roadRects.length > 0) {
    paintMaskRects(ctx, roadRects, scale, tokenColor(styles, ROAD_CASING_VAR, '#241f12'), bleed)
    paintMaskRects(ctx, roadRects, scale, tokenColor(styles, ROAD_FILL_VAR, '#e6c886'), 0)
  }

  const image = ctx.getImageData(0, 0, canvas.width, canvas.height)
  const data = image.data
  for (let y = 0; y < canvas.height; y++) {
    for (let x = 0; x < canvas.width; x++) {
      const idx = (y * canvas.width + x) * 4
      const d = ditherOffset(x, y)
      data[idx] = Math.max(0, Math.min(255, data[idx] + d))
      data[idx + 1] = Math.max(0, Math.min(255, data[idx + 1] + d))
      data[idx + 2] = Math.max(0, Math.min(255, data[idx + 2] + d))
    }
  }
  ctx.putImageData(image, 0, 0)
  imageUrl.value = canvas.toDataURL()
}

watch(
  [() => store.worldSnapshot, () => props.roads, () => props.rivers],
  renderTerrain,
  { immediate: true },
)
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
  /* Blend, don't pixelate: the canvas is pre-dithered and upscaled, so browser
     scaling should interpolate rather than snap to hard cell edges. */
  image-rendering: auto;
}
</style>
