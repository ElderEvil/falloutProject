<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useMapStore } from '../stores/map'
import { ATLAS_TERRAIN_ORDER, ATLAS_TERRAIN_VAR, MAP_UNITS } from '../utils/atlasProjection'
import { maskToRects, type MaskRect } from '../utils/maskGeometry'
import type { TerrainType } from '../models/terrain'
import type { WorldSnapshotRead } from '../models/map'

const props = withDefaults(
  defineProps<{
    /** Explicit snapshot for previews; falls back to the map store when omitted. */
    snapshot?: WorldSnapshotRead | null
    palette?: 'atlas'
    /** Display-only road mask: flat, sorted tile indices over the snapshot grid. */
    roads?: readonly number[]
    /** Display-only river mask: flat, sorted tile indices over the snapshot grid. */
    rivers?: readonly number[]
    /** Smoothed float road edges; preferred over the mask when present. */
    roadEdges?: readonly RoadEdge[]
    /** Optional illustrated terrain drawn under the masks (preview only). */
    underlayUrl?: string
  }>(),
  {
    roads: () => [],
    rivers: () => [],
    roadEdges: () => [],
  },
)

type UnderlayState = 'none' | 'pending' | 'loaded' | 'failed'
interface RoadEdge {
  class?: string
  points?: readonly (readonly number[])[]
}
interface TownShape {
  points?: readonly (readonly number[])[]
  blocks?: readonly (readonly (readonly number[])[])[]
}

const store = useMapStore()
const snapshot = computed(() =>
  props.snapshot === undefined ? store.worldSnapshot : props.snapshot
)
const towns = computed(() => (snapshot.value?.towns ?? []) as TownShape[])
const imageUrl = ref('')
const underlayState = ref<UnderlayState>('none')
let underlayImage: HTMLImageElement | null = null
let underlayRequest = 0

function loadUnderlay(url: string | undefined): void {
  const request = ++underlayRequest
  underlayImage = null
  if (!url) {
    if (underlayState.value !== 'none') {
      underlayState.value = 'none'
      renderTerrain()
    }
    return
  }
  underlayState.value = 'pending'
  const image = new Image()
  image.onload = () => {
    if (request !== underlayRequest) return
    underlayImage = image
    underlayState.value = 'loaded'
    renderTerrain()
  }
  image.onerror = () => {
    if (request !== underlayRequest) return
    underlayState.value = 'failed'
    renderTerrain()
  }
  image.src = url
}

// Backend-owned terrain: renders the persisted snapshot verbatim. No local
// generation, no fallback geography — a missing snapshot renders nothing rather
// than a second, divergent world. Road edges are display-only vector polylines;
// the legacy road/river masks remain a v2 fallback. Neither carries movement authority.
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
const COUNTRY_FILL_VAR = '--color-road-country'
const COUNTRY_CASING_VAR = '--color-road-country-casing'
const TOWN_FILL_VAR = '--color-road-town'
const TOWN_CASING_VAR = '--color-road-town-casing'
const TOWN_GROUND_VAR = '--color-town-ground'
const TOWN_BLOCK_VAR = '--color-town-block'
const TOWN_BUILDING_VAR = '--color-town-building'
const HIGHWAY_FILL_VAR = '--color-road-highway'
const HIGHWAY_CASING_VAR = '--color-road-highway-casing'
const HIGHWAY_MARKING_VAR = '--color-road-highway-marking'
const WATER_FILL_VAR = '--color-terrain-water'

/** Deterministic per-pixel brightness offset in [-DITHER_RANGE, DITHER_RANGE]. */
function ditherOffset(x: number, y: number): number {
  let h = (x * 374761393 + y * 668265263) | 0
  h = Math.imul(h ^ (h >>> 13), 1274126177)
  h ^= h >>> 16
  return ((h & 0xff) / 255 - 0.5) * 2 * DITHER_RANGE
}

function tokenColor(styles: CSSStyleDeclaration, name: string): string {
  return styles.getPropertyValue(name).trim()
}

function resolveTerrainColors(): Record<TerrainType, string> {
  const styles = getComputedStyle(document.documentElement)
  const colors = {} as Record<TerrainType, string>
  for (const terrain of ATLAS_TERRAIN_ORDER) {
    const token =
      props.palette === 'atlas' ? `--color-atlas-${terrain}` : ATLAS_TERRAIN_VAR[terrain]
    colors[terrain] = tokenColor(styles, token) || '#000000'
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

function strokeRoadEdges(
  ctx: CanvasRenderingContext2D,
  edges: readonly RoadEdge[],
  width: number,
  scale: number,
  color: string,
  lineWidth: number,
  dash?: readonly number[],
): boolean {
  if (edges.length === 0 || !color) return false
  const unit = (MAP_UNITS / width) * scale
  ctx.strokeStyle = color
  ctx.lineWidth = lineWidth * scale
  ctx.setLineDash(dash ?? [])
  ctx.lineJoin = 'round'
  ctx.lineCap = 'round'
  for (const edge of edges) {
    const points = edge.points
    if (!points || points.length < 2) continue
    ctx.beginPath()
    ctx.moveTo(points[0][0] * unit, points[0][1] * unit)
    for (let i = 1; i < points.length; i++) {
      ctx.lineTo(points[i][0] * unit, points[i][1] * unit)
    }
    ctx.stroke()
  }
  ctx.setLineDash([])
  return true
}

function paintTownGround(
  ctx: CanvasRenderingContext2D,
  towns: readonly TownShape[],
  width: number,
  scale: number,
  color: string,
): void {
  if (!color || towns.length === 0) return
  const unit = (MAP_UNITS / width) * scale
  ctx.save()
  ctx.filter = 'blur(1.4px)'
  ctx.fillStyle = color
  for (const town of towns) {
    const points = town.points
    if (!points || points.length < 3) continue
    ctx.beginPath()
    ctx.moveTo(points[0][0] * unit, points[0][1] * unit)
    for (let index = 1; index < points.length; index++) {
      ctx.lineTo(points[index][0] * unit, points[index][1] * unit)
    }
    ctx.closePath()
    ctx.fill()
  }
  ctx.restore()
}

function paintTownBlocks(
  ctx: CanvasRenderingContext2D,
  towns: readonly TownShape[],
  width: number,
  scale: number,
  color: string,
  buildingColor: string,
): void {
  if (!color || towns.length === 0) return
  const unit = (MAP_UNITS / width) * scale
  ctx.save()
  for (const town of towns) {
    for (const block of town.blocks ?? []) {
      if (block.length < 3) continue
      ctx.fillStyle = color
      ctx.beginPath()
      ctx.moveTo(block[0][0] * unit, block[0][1] * unit)
      for (let index = 1; index < block.length; index++) {
        ctx.lineTo(block[index][0] * unit, block[index][1] * unit)
      }
      ctx.closePath()
      ctx.fill()
      if (!buildingColor) continue
      const centerX = block.reduce((sum, point) => sum + point[0], 0) / block.length
      const centerY = block.reduce((sum, point) => sum + point[1], 0) / block.length
      ctx.fillStyle = buildingColor
      ctx.beginPath()
      for (let index = 0; index < block.length; index++) {
        const x = centerX + (block[index][0] - centerX) * 0.62
        const y = centerY + (block[index][1] - centerY) * 0.62
        if (index === 0) ctx.moveTo(x * unit, y * unit)
        else ctx.lineTo(x * unit, y * unit)
      }
      ctx.closePath()
      ctx.fill()
    }
  }
  ctx.restore()
}

function paintWaterLayer(
  ctx: CanvasRenderingContext2D,
  canvas: HTMLCanvasElement,
  world: { terrain: readonly string[] },
  width: number,
  height: number,
  color: string,
): void {
  if (!color) return
  const mask = document.createElement('canvas')
  mask.width = width
  mask.height = height
  const maskCtx = mask.getContext('2d')
  if (maskCtx === null) return
  maskCtx.fillStyle = color
  for (let index = 0; index < world.terrain.length; index++) {
    if (world.terrain[index] === 'water') {
      maskCtx.fillRect(index % width, Math.floor(index / width), 1, 1)
    }
  }
  for (const index of props.rivers) {
    maskCtx.fillRect(index % width, Math.floor(index / width), 1, 1)
  }
  ctx.save()
  ctx.imageSmoothingEnabled = true
  ctx.filter = 'blur(0.6px)'
  ctx.drawImage(mask, 0, 0, canvas.width, canvas.height)
  ctx.restore()
}

function renderTerrain(): void {
  const world = snapshot.value
  if (world === null) {
    imageUrl.value = ''
    return
  }
  const { width, height } = world
  const cells = document.createElement('canvas')
  cells.width = width
  cells.height = height
  const cellCtx = cells.getContext('2d')
  if (cellCtx === null) {
    imageUrl.value = ''
    return
  }
  const colors = resolveTerrainColors()
  for (let i = 0; i < world.terrain.length; i++) {
    cellCtx.fillStyle = colors[world.terrain[i] as TerrainType] ?? '#000000'
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

  if (underlayImage !== null) {
    ctx.drawImage(underlayImage, 0, 0, canvas.width, canvas.height)
  }

  const styles = getComputedStyle(document.documentElement)
  const scale = canvas.width / MAP_UNITS
  const tile = MAP_UNITS / width
  const bleed = tile * MASK_BLEED
  paintTownGround(ctx, towns.value, width, scale, tokenColor(styles, TOWN_GROUND_VAR))
  paintTownBlocks(
    ctx,
    towns.value,
    width,
    scale,
    tokenColor(styles, TOWN_BLOCK_VAR),
    tokenColor(styles, TOWN_BUILDING_VAR),
  )
  paintWaterLayer(ctx, canvas, world, width, height, tokenColor(styles, WATER_FILL_VAR))
  const casing = tokenColor(styles, ROAD_CASING_VAR)
  const fill = tokenColor(styles, ROAD_FILL_VAR)
  const countryCasing = tokenColor(styles, COUNTRY_CASING_VAR)
  const countryFill = tokenColor(styles, COUNTRY_FILL_VAR)
  const townCasing = tokenColor(styles, TOWN_CASING_VAR)
  const townFill = tokenColor(styles, TOWN_FILL_VAR)
  const highwayCasing = tokenColor(styles, HIGHWAY_CASING_VAR)
  const highwayFill = tokenColor(styles, HIGHWAY_FILL_VAR)
  const highwayMarking = tokenColor(styles, HIGHWAY_MARKING_VAR)
  const accessEdges = props.roadEdges.filter((edge) => edge.class === 'access')
  const countryEdges = props.roadEdges.filter((edge) => edge.class === 'country')
  const townEdges = props.roadEdges.filter((edge) => edge.class === 'town')
  const highwayEdges = props.roadEdges.filter((edge) => edge.class === 'highway')
  let roadEdgesDrawn = false
  if (props.roadEdges.length > 0) {
    roadEdgesDrawn = strokeRoadEdges(ctx, accessEdges, width, scale, countryCasing, tile * 0.18) || roadEdgesDrawn
    roadEdgesDrawn = strokeRoadEdges(ctx, accessEdges, width, scale, countryFill, tile * 0.09) || roadEdgesDrawn
    roadEdgesDrawn = strokeRoadEdges(ctx, countryEdges, width, scale, countryCasing, tile * 0.34) || roadEdgesDrawn
    roadEdgesDrawn = strokeRoadEdges(ctx, countryEdges, width, scale, countryFill, tile * 0.17) || roadEdgesDrawn
    roadEdgesDrawn = strokeRoadEdges(ctx, townEdges, width, scale, townCasing, tile * 0.4) || roadEdgesDrawn
    roadEdgesDrawn = strokeRoadEdges(ctx, townEdges, width, scale, townFill, tile * 0.22) || roadEdgesDrawn
    if (highwayEdges.length > 0) {
      roadEdgesDrawn = strokeRoadEdges(ctx, highwayEdges, width, scale, highwayCasing, tile * 0.8) || roadEdgesDrawn
      roadEdgesDrawn = strokeRoadEdges(ctx, highwayEdges, width, scale, highwayFill, tile * 0.45) || roadEdgesDrawn
      strokeRoadEdges(ctx, highwayEdges, width, scale, highwayMarking, tile * 0.09, [tile * 1.1, tile * 0.75])
    }
  }
  if (!roadEdgesDrawn) {
    const roadRects = maskToRects(props.roads, width)
    if (roadRects.length > 0) {
      if (casing) paintMaskRects(ctx, roadRects, scale, casing, bleed)
      if (fill) paintMaskRects(ctx, roadRects, scale, fill, 0)
    }
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
  [
    snapshot,
    () => props.palette,
    () => props.roads,
    () => props.rivers,
    () => props.roadEdges,
  ],
  renderTerrain,
  { immediate: true },
)
watch(() => props.underlayUrl, loadUnderlay, { immediate: true })
onBeforeUnmount(() => {
  underlayRequest += 1
  underlayImage = null
  imageUrl.value = ''
})
</script>

<template>
  <g
    class="atlas-terrain"
    aria-hidden="true"
    v-bind="{
      'data-underlay': underlayState,
      'data-road-mode': roadEdges.length > 0 ? 'edges' : 'masks',
      'data-town-mode': towns.length > 0 ? 'ground' : 'none',
    }"
  >
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
