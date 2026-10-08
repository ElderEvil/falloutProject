<script setup lang="ts">
/**
 * MapPrototypeView — dev-only visual prototype for the tile-based overworld
 * generator. Throwaway PoC: render a generated world on a canvas, tune seeds,
 * inspect the validation report, and click around to test A* routing.
 *
 * Everything is client-side and local: no API, no stores, no persistence.
 * Generation always goes through `generateWorld` from ./worldgen — nothing is
 * reimplemented here.
 */
import { computed, onMounted, onUnmounted, ref, shallowRef } from 'vue'
import { Button } from '@/core/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/core/components/ui/card'
import { Input } from '@/core/components/ui/input'
import {
  DEFAULT_WORLD_CONFIG,
  HOURS_PER_COST,
  ROAD_TRAVEL_DISCOUNT,
  TRAVEL_COST,
  ANCHOR_CONSTRAINT_VERSION,
  SHARED_FIXTURE_VERSION,
  SHARED_ANCHOR_FIXTURES,
  findPath,
  generateWorld,
  type GeneratedWorld,
  type MapLocation,
  type PathOptions,
  type TerrainType,
  type VaultSlot,
} from '@/modules/map/utils/atlasWorldgen'
import { isExplored, isVisible, revealDisc } from './fog'
import { isFrontierTile, scoutBand, scoutProbeTarget } from './scout'
import {
  fetchProdMap,
  registryToCanvas,
  type ProdLocation,
  type PublicAnchor,
} from './prodMap'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { handleStoreError } from '@/core/utils/errorHandler'

const TILE = 8

interface Point {
  x: number
  y: number
}

interface RouteResult {
  path: Point[]
  cost: number
  hours: number
}

// Muted terrain palette — deliberately desaturated so the green CRT accents pop.
const costLabel = (cost: number): string => (Number.isFinite(cost) ? String(Math.round(cost * 100) / 100) : 'impassable')

const TERRAIN_META = {
  wasteland: { color: '#45402e', swatch: 'bg-[#45402e]' },
  forest: { color: '#2e4030', swatch: 'bg-[#2e4030]' },
  ruins: { color: '#5c5144', swatch: 'bg-[#5c5144]' },
  hills: { color: '#3a3228', swatch: 'bg-[#3a3228]' },
  water: { color: '#2e3d4a', swatch: 'bg-[#2e3d4a]' },
} satisfies Record<TerrainType, { color: string; swatch: string }>

const hexToRgb = (hex: string): [number, number, number] => {
  const value = Number.parseInt(hex.slice(1), 16)
  return [(value >> 16) & 0xff, (value >> 8) & 0xff, value & 0xff]
}

// Precomputed RGB for the biome-blend blur — derived from TERRAIN_META so the
// palette stays the single source of truth.
const TERRAIN_RGB: Record<TerrainType, [number, number, number]> = {
  wasteland: hexToRgb(TERRAIN_META.wasteland.color),
  forest: hexToRgb(TERRAIN_META.forest.color),
  ruins: hexToRgb(TERRAIN_META.ruins.color),
  hills: hexToRgb(TERRAIN_META.hills.color),
  water: hexToRgb(TERRAIN_META.water.color),
}

const FALLBACK_LOCATION_COLOR = '#9aa0a6'

const TERRAIN_LEGEND: Array<{ type: TerrainType; swatch: string; cost: string }> = (
  Object.keys(TERRAIN_META) as TerrainType[]
).map(t => ({
  type: t,
  swatch: TERRAIN_META[t].swatch,
  cost: t === 'water' ? 'impassable' : costLabel(TRAVEL_COST[t]),
}))



// ── Player-facing marker silhouettes ────────────────────────────────────
// Icons are ~10–14px vector silhouettes centered on their tile — roughly 1.5
// tiles wide, so dense maps (up to 600 locations) will overlap. That density
// trade-off is accepted for readability; the Locations density control is the
// decluttering mechanism, not icon culling.

const ICON_OUTLINE = 'rgba(0, 0, 0, 0.85)'

type IconDrawer = (ctx: CanvasRenderingContext2D, cx: number, cy: number, color: string) => void

/** Stroke a path twice: dark outline underneath, then the kind color on top. */
const strokeWithOutline = (ctx: CanvasRenderingContext2D, color: string, width: number, draw: () => void): void => {
  ctx.lineWidth = width + 1.6
  ctx.strokeStyle = ICON_OUTLINE
  draw()
  ctx.lineWidth = width
  ctx.strokeStyle = color
  draw()
}

/** Vault door — gear ring; claimed vaults render as a filled gear. */
const drawVaultDoor = (
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  color: string,
  claimed: boolean,
): void => {
  ctx.save()
  ctx.translate(cx, cy)
  ctx.fillStyle = color
  ctx.strokeStyle = ICON_OUTLINE
  ctx.lineWidth = 1.4
  if (claimed) {
    ctx.beginPath()
    ctx.arc(0, 0, 5.5, 0, Math.PI * 2)
    ctx.fill()
    for (let i = 0; i < 8; i++) {
      ctx.save()
      ctx.rotate((i * Math.PI) / 4)
      ctx.fillRect(4.5, -1.5, 2, 3)
      ctx.restore()
    }
    ctx.beginPath()
    ctx.arc(0, 0, 5.5, 0, Math.PI * 2)
    ctx.stroke()
    ctx.fillStyle = ICON_OUTLINE
    ctx.beginPath()
    ctx.arc(0, 0, 1.8, 0, Math.PI * 2)
    ctx.fill()
  } else {
    const ring = (): void => {
      ctx.beginPath()
      ctx.arc(0, 0, 5.5, 0, Math.PI * 2)
      ctx.stroke()
      for (let i = 0; i < 8; i++) {
        ctx.save()
        ctx.rotate((i * Math.PI) / 4)
        ctx.beginPath()
        ctx.moveTo(2.2, 0)
        ctx.lineTo(4.8, 0)
        ctx.stroke()
        ctx.restore()
      }
      ctx.beginPath()
      ctx.arc(0, 0, 2.2, 0, Math.PI * 2)
      ctx.stroke()
    }
    strokeWithOutline(ctx, color, 1.4, ring)
  }
  ctx.restore()
}

/** Red Rocket — rocket silhouette with nose cone, fins and porthole. */
const drawRocket = (ctx: CanvasRenderingContext2D, cx: number, cy: number, color: string): void => {
  ctx.save()
  ctx.translate(cx, cy)
  ctx.fillStyle = color
  ctx.strokeStyle = ICON_OUTLINE
  ctx.lineWidth = 1.2
  ctx.beginPath()
  ctx.moveTo(-2.2, 3.5)
  ctx.lineTo(-2.2, -3.5)
  ctx.quadraticCurveTo(-2.2, -6, 0, -6)
  ctx.quadraticCurveTo(2.2, -6, 2.2, -3.5)
  ctx.lineTo(2.2, 3.5)
  ctx.closePath()
  ctx.fill()
  ctx.stroke()
  ctx.beginPath()
  ctx.moveTo(-2.2, -3.5)
  ctx.lineTo(0, -8)
  ctx.lineTo(2.2, -3.5)
  ctx.closePath()
  ctx.fill()
  ctx.stroke()
  ctx.beginPath()
  ctx.moveTo(-2.2, 1)
  ctx.lineTo(-5, 4.5)
  ctx.lineTo(-2.2, 3.5)
  ctx.closePath()
  ctx.fill()
  ctx.stroke()
  ctx.beginPath()
  ctx.moveTo(2.2, 1)
  ctx.lineTo(5, 4.5)
  ctx.lineTo(2.2, 3.5)
  ctx.closePath()
  ctx.fill()
  ctx.stroke()
  ctx.fillStyle = ICON_OUTLINE
  ctx.beginPath()
  ctx.arc(0, -1.5, 1.3, 0, Math.PI * 2)
  ctx.fill()
  ctx.restore()
}

/** Super Duper Mart — storefront awning with scalloped edge and door. */
const drawStore = (ctx: CanvasRenderingContext2D, cx: number, cy: number, color: string): void => {
  ctx.save()
  ctx.translate(cx, cy)
  ctx.fillStyle = color
  ctx.strokeStyle = ICON_OUTLINE
  ctx.lineWidth = 1.2
  ctx.fillRect(-5.5, -5, 11, 4)
  ctx.strokeRect(-5.5, -5, 11, 4)
  for (let i = 0; i < 4; i++) {
    ctx.beginPath()
    ctx.arc(-4.125 + i * 2.75, -1, 1.375, 0, Math.PI)
    ctx.fill()
    ctx.stroke()
  }
  ctx.fillRect(-4.5, 0, 9, 3.5)
  ctx.strokeRect(-4.5, 0, 9, 3.5)
  ctx.fillStyle = ICON_OUTLINE
  ctx.fillRect(-1, 1.2, 2, 2.3)
  ctx.restore()
}

/** Radio Tower — lattice tower with signal arcs above the apex. */
const drawTower = (ctx: CanvasRenderingContext2D, cx: number, cy: number, color: string): void => {
  ctx.save()
  ctx.translate(cx, cy)
  const lattice = (): void => {
    ctx.beginPath()
    ctx.moveTo(-3.2, 5)
    ctx.lineTo(0, -4)
    ctx.lineTo(3.2, 5)
    ctx.stroke()
    for (const y of [4, 2, 0, -2]) {
      const w = (3.2 * (5 - y)) / 9
      ctx.beginPath()
      ctx.moveTo(-w, y)
      ctx.lineTo(w, y)
      ctx.stroke()
    }
    for (const y of [4, 2, 0]) {
      const w1 = (3.2 * (5 - y)) / 9
      const w2 = (3.2 * (5 - (y - 2))) / 9
      ctx.beginPath()
      ctx.moveTo(-w1, y)
      ctx.lineTo(w2, y - 2)
      ctx.moveTo(w1, y)
      ctx.lineTo(-w2, y - 2)
      ctx.stroke()
    }
  }
  strokeWithOutline(ctx, color, 1.2, lattice)
  const arcs = (): void => {
    ctx.beginPath()
    ctx.arc(0, -4, 2.2, Math.PI * 0.15, Math.PI * 0.85, true)
    ctx.stroke()
    ctx.beginPath()
    ctx.arc(0, -4, 3.8, Math.PI * 0.25, Math.PI * 0.75, true)
    ctx.stroke()
  }
  strokeWithOutline(ctx, color, 1.2, arcs)
  ctx.restore()
}

/** Raider Camp — hostile skull mark. */
const drawSkull = (ctx: CanvasRenderingContext2D, cx: number, cy: number, color: string): void => {
  ctx.save()
  ctx.translate(cx, cy)
  ctx.fillStyle = color
  ctx.strokeStyle = ICON_OUTLINE
  ctx.lineWidth = 1.2
  ctx.beginPath()
  ctx.arc(0, -1.5, 5, Math.PI, 0)
  ctx.lineTo(5, 3)
  ctx.lineTo(-5, 3)
  ctx.closePath()
  ctx.fill()
  ctx.stroke()
  ctx.fillStyle = ICON_OUTLINE
  ctx.beginPath()
  ctx.arc(-2, -1, 1.4, 0, Math.PI * 2)
  ctx.fill()
  ctx.beginPath()
  ctx.arc(2, -1, 1.4, 0, Math.PI * 2)
  ctx.fill()
  ctx.strokeStyle = ICON_OUTLINE
  ctx.beginPath()
  ctx.moveTo(-3, 1.5)
  ctx.lineTo(-3, 3)
  ctx.moveTo(0, 1.5)
  ctx.lineTo(0, 3)
  ctx.moveTo(3, 1.5)
  ctx.lineTo(3, 3)
  ctx.stroke()
  ctx.restore()
}

/** Abandoned Factory — sawtooth-roofed hall with chimney and smoke. */
const drawFactory = (ctx: CanvasRenderingContext2D, cx: number, cy: number, color: string): void => {
  ctx.save()
  ctx.translate(cx, cy)
  ctx.fillStyle = color
  ctx.strokeStyle = ICON_OUTLINE
  ctx.lineWidth = 1.2
  ctx.fillRect(2.5, -6, 2, 3)
  ctx.strokeRect(2.5, -6, 2, 3)
  ctx.beginPath()
  ctx.arc(3.5, -7.5, 1.2, 0, Math.PI * 2)
  ctx.fill()
  ctx.stroke()
  ctx.beginPath()
  ctx.moveTo(-5.5, 2.5)
  ctx.lineTo(-5.5, -2)
  ctx.lineTo(-2.75, -4.5)
  ctx.lineTo(0, -2)
  ctx.lineTo(2.75, -4.5)
  ctx.lineTo(5.5, -2)
  ctx.lineTo(5.5, 2.5)
  ctx.closePath()
  ctx.fill()
  ctx.stroke()
  ctx.fillStyle = ICON_OUTLINE
  ctx.fillRect(-1, 0.5, 2, 2)
  ctx.restore()
}

/** Settlement — clustered houses with pitched roofs. */
const drawHouses = (ctx: CanvasRenderingContext2D, cx: number, cy: number, color: string): void => {
  ctx.save()
  ctx.translate(cx, cy)
  ctx.fillStyle = color
  ctx.strokeStyle = ICON_OUTLINE
  ctx.lineWidth = 1.2
  ctx.fillRect(-6, -1.5, 5, 4.5)
  ctx.strokeRect(-6, -1.5, 5, 4.5)
  ctx.beginPath()
  ctx.moveTo(-6.5, -1.5)
  ctx.lineTo(-3.5, -5)
  ctx.lineTo(-0.5, -1.5)
  ctx.closePath()
  ctx.fill()
  ctx.stroke()
  ctx.fillRect(1, -0.5, 5, 3.5)
  ctx.strokeRect(1, -0.5, 5, 3.5)
  ctx.beginPath()
  ctx.moveTo(0.5, -0.5)
  ctx.lineTo(3.5, -4)
  ctx.lineTo(6.5, -0.5)
  ctx.closePath()
  ctx.fill()
  ctx.stroke()
  ctx.fillRect(-5, -3.5, 1.5, 2)
  ctx.strokeRect(-5, -3.5, 1.5, 2)
  ctx.restore()
}

/** Water Treatment — water drop with highlight. */
const drawWaterDrop = (ctx: CanvasRenderingContext2D, cx: number, cy: number, color: string): void => {
  ctx.save()
  ctx.translate(cx, cy)
  ctx.fillStyle = color
  ctx.strokeStyle = ICON_OUTLINE
  ctx.lineWidth = 1.2
  ctx.beginPath()
  ctx.moveTo(0, -6.5)
  ctx.bezierCurveTo(3.8, -2.5, 4.5, -0.5, 4.5, 1.5)
  ctx.arc(0, 1.5, 4.5, 0, Math.PI)
  ctx.bezierCurveTo(-4.5, -0.5, -3.8, -2.5, 0, -6.5)
  ctx.closePath()
  ctx.fill()
  ctx.stroke()
  ctx.fillStyle = ICON_OUTLINE
  ctx.beginPath()
  ctx.arc(-1.4, 0.8, 1.1, 0, Math.PI * 2)
  ctx.fill()
  ctx.restore()
}

/** Supply Cache — small rounded crate with a lid band and diagonal brace. */
const drawSupplyCrate = (ctx: CanvasRenderingContext2D, cx: number, cy: number, color: string): void => {
  ctx.save()
  ctx.translate(cx, cy)
  ctx.fillStyle = color
  ctx.strokeStyle = ICON_OUTLINE
  ctx.lineWidth = 1.2
  const r = 1.5
  ctx.beginPath()
  ctx.moveTo(-5 + r, -3.5)
  ctx.lineTo(5 - r, -3.5)
  ctx.quadraticCurveTo(5, -3.5, 5, -3.5 + r)
  ctx.lineTo(5, 4 - r)
  ctx.quadraticCurveTo(5, 4, 5 - r, 4)
  ctx.lineTo(-5 + r, 4)
  ctx.quadraticCurveTo(-5, 4, -5, 4 - r)
  ctx.lineTo(-5, -3.5 + r)
  ctx.quadraticCurveTo(-5, -3.5, -5 + r, -3.5)
  ctx.closePath()
  ctx.fill()
  ctx.stroke()
  ctx.fillRect(-5, -3.5, 10, 1.8)
  ctx.strokeRect(-5, -3.5, 10, 1.8)
  ctx.beginPath()
  ctx.moveTo(-4, 3.5)
  ctx.lineTo(4, -1.5)
  ctx.stroke()
  ctx.restore()
}

/** Generic diamond fallback for LocationKind members not yet in LOCATION_ICONS. */
const drawUnknown = (ctx: CanvasRenderingContext2D, cx: number, cy: number, color: string): void => {
  ctx.save()
  ctx.translate(cx, cy)
  ctx.fillStyle = color
  ctx.strokeStyle = ICON_OUTLINE
  ctx.lineWidth = 1.2
  ctx.beginPath()
  ctx.moveTo(0, -5.5)
  ctx.lineTo(4.5, 0)
  ctx.lineTo(0, 5.5)
  ctx.lineTo(-4.5, 0)
  ctx.closePath()
  ctx.fill()
  ctx.stroke()
  ctx.restore()
}

// Single per-kind table driving marker color, legend swatch/label, and icon.
// Record<string, ...> so a future LocationKind member falls back instead of
// breaking the build.
const LOCATION_META: Record<string, { color: string; swatch: string; label: string; icon: IconDrawer }> = {
  settlement: { color: '#00ff00', swatch: 'bg-[#00ff00]', label: 'settlement', icon: drawHouses },
  red_rocket: { color: '#ff6b6b', swatch: 'bg-[#ff6b6b]', label: 'red rocket', icon: drawRocket },
  super_duper_mart: { color: '#ffd43b', swatch: 'bg-[#ffd43b]', label: 'super duper mart', icon: drawStore },
  abandoned_factory: { color: '#c8b9ae', swatch: 'bg-[#c8b9ae]', label: 'abandoned factory', icon: drawFactory },
  radio_tower: { color: '#00d9ff', swatch: 'bg-[#00d9ff]', label: 'radio tower', icon: drawTower },
  water_treatment: { color: '#4dabf7', swatch: 'bg-[#4dabf7]', label: 'water treatment', icon: drawWaterDrop },
  raider_camp: { color: '#ff7043', swatch: 'bg-[#ff7043]', label: 'raider camp', icon: drawSkull },
  supply_cache: { color: '#d4a24e', swatch: 'bg-[#d4a24e]', label: 'supply cache', icon: drawSupplyCrate },
}

const locationMeta = (kind: string): { color: string; swatch: string; label: string; icon: IconDrawer } => {
  const m = LOCATION_META[kind]
  if (m !== undefined) return m
  return { color: FALLBACK_LOCATION_COLOR, swatch: 'bg-[#9aa0a6]', label: kind.replace(/_/g, ' '), icon: drawUnknown }
}

const LOCATION_LEGEND: Array<{ kind: string; swatch: string; label: string }> = Object.keys(LOCATION_META).map(k => ({
  kind: k,
  swatch: LOCATION_META[k].swatch,
  label: LOCATION_META[k].label,
}))

type LayerKey = 'terrain' | 'grid' | 'vaults' | 'locations' | 'roads' | 'origin' | 'route'

const LAYER_TOGGLES: Array<{ key: LayerKey; label: string }> = [
  { key: 'terrain', label: 'Terrain' },
  { key: 'grid', label: 'Grid' },
  { key: 'vaults', label: 'Vault slots' },
  { key: 'locations', label: 'Locations' },
  { key: 'roads', label: 'Roads' },
  { key: 'origin', label: 'Origin' },
  { key: 'route', label: 'Route' },
]

// Minecraft-style biome blend: radius r blends each cell over a (2r+1)×(2r+1)
// neighborhood in cell space. Default 3×3 (r = 1) — just enough to soften
// seams without muddying biomes.
const BLEND_OPTIONS: Array<{ label: string; radius: number }> = [
  { label: 'Off', radius: 0 },
  { label: '3×3', radius: 1 },
  { label: '5×5', radius: 2 },
  { label: '7×7', radius: 3 },
  { label: '9×9', radius: 4 },
  { label: '15×15', radius: 7 },
]

const canvasRef = ref<HTMLCanvasElement | null>(null)
const seedInput = ref(DEFAULT_WORLD_CONFIG.seed)
const locationCountInput = ref(String(DEFAULT_WORLD_CONFIG.locationCount))
const world = shallowRef<GeneratedWorld>(generateWorld())
const playerIcons = ref(true)
const showMinorCaches = ref(true)
const blendRadius = ref(1)
// Cached biome-blended grid buffer — rebuilt only when the world or the blend
// radius changes, so hover/route redraws stay cheap.
let blendedBuffer: HTMLCanvasElement | null = null
let blendedBufferRadius = -1
const layers = ref<Record<LayerKey, boolean>>({
  terrain: true,
  grid: false, // hidden by default; still available via the toggle
  vaults: true,
  locations: true,
  roads: true,
  origin: true,
  route: true,
})

const claimedIds = ref<number[]>([])
const hoverTile = ref<Point | null>(null)
const routeStart = ref<Point | null>(null)
const routeEnd = ref<Point | null>(null)
const routeResult = ref<RouteResult | null>(null)
const routeUnreachable = ref(false)
const selectedLocation = ref<MapLocation | null>(null)
const selectedVault = ref<VaultSlot | null>(null)

const ORIGIN_REVEAL = 8
const CLAIM_REVEAL = 6
const SIGHT_RADIUS = 5

const explored = ref<Uint8Array>(new Uint8Array(0))
const showAll = ref(false)
const playerPreview = ref(false)
const roadDiscountEnabled = ref(true)

// Player preview enforces the visibility contract; developer mode (not preview)
// and the show-all inspection toggle bypass it for diagnostics.
const visibilityEnforced = computed(() => playerPreview.value && !showAll.value)
const tileVisible = (x: number, y: number): boolean =>
  isVisible(explored.value, world.value.config.width, world.value.config.height, x, y, !visibilityEnforced.value)

// One options object for every path call, so routing and ETA can never disagree
// about visibility or the road-discount experiment.
const pathOptions = (): PathOptions => ({
  explored: visibilityEnforced.value ? explored.value : undefined,
  roadDiscount: roadDiscountEnabled.value ? ROAD_TRAVEL_DISCOUNT : 1,
})

const recomputeRoute = (): void => {
  const start = routeStart.value
  const end = routeEnd.value
  if (start === null || end === null) return
  const result = findPath(world.value, start, end, pathOptions())
  if (result === null) {
    routeResult.value = null
    routeUnreachable.value = true
  } else {
    routeResult.value = result
    routeUnreachable.value = false
  }
}
const routeUnknown = ref(false)
const prodVaultId = ref('')
const prodLocations = ref<ProdLocation[]>([])
const prodAnchors = ref<PublicAnchor[]>([])
const anchoredPreview = ref(false)
const showTerrainChanges = ref(true)
const fixtureScenario = ref<'compatible' | 'conflict'>('compatible')
const baseWorld = shallowRef<GeneratedWorld | null>(null)
const fixtureAnchors = computed(() => SHARED_ANCHOR_FIXTURES.filter(a => fixtureScenario.value === 'conflict' || a.id !== 'fixture-conflict'))
const changedTiles = computed(() => baseWorld.value === null ? [] : world.value.terrain.flatMap((t, i) =>
  t !== baseWorld.value?.terrain[i] ? [i] : [],
))
const prodTotal = ref(0)
const prodLoading = ref(false)
const prodError = ref<string | null>(null)
const prodShow = ref(false)
const expedition = ref<{ path: Array<Point>; index: number } | null>(null)
let expeditionTimer: number | null = null
// Visible location ids captured when an expedition starts, so arrival can report
// exactly what the journey revealed.
let expeditionKnownBefore: Set<number> | null = null

// Scout loop: pick a revealed frontier tile, send a scout past it on an
// approximate duration, and let arrival do the discovering.
const scoutMode = ref(false)
const scoutTarget = ref<Point | null>(null)
const scoutHint = ref('')
const discoveries = ref<MapLocation[]>([])
const SCOUT_PROBE = 8

const scoutPreview = computed<{ band: { low: number; high: number }; path: Point[] } | null>(() => {
  const target = scoutTarget.value
  if (target === null) return null
  const result = findPath(world.value, world.value.origin, target, pathOptions())
  if (result === null) return null
  return { band: scoutBand(result.hours), path: result.path }
})

const revealAt = (cx: number, cy: number, r: number): void => {
  const { width, height } = world.value.config
  const next = explored.value.slice()
  revealDisc(next, width, height, cx, cy, r)
  explored.value = next
}

const stopExpedition = (): void => {
  if (expeditionTimer !== null) {
    window.clearInterval(expeditionTimer)
    expeditionTimer = null
  }
  expedition.value = null
}

const cancelExpedition = (): void => {
  stopExpedition()
  redraw()
}

const resetFog = (): void => {
  stopExpedition()
  const { width, height } = world.value.config
  explored.value = new Uint8Array(width * height)
  revealAt(world.value.origin.x, world.value.origin.y, ORIGIN_REVEAL)
  selectedLocation.value = null
  selectedVault.value = null
  routeUnknown.value = false
  scoutTarget.value = null
  scoutHint.value = ''
  redraw()
}

const runExpedition = (path: Point[]): void => {
  if (path.length === 0 || expedition.value !== null) return
  stopExpedition()
  expeditionKnownBefore = new Set(
    world.value.locations.filter(l => tileVisible(l.x, l.y)).map(l => l.id),
  )
  const tick = Math.min(150, Math.max(30, Math.round(4000 / path.length)))
  revealAt(path[0].x, path[0].y, SIGHT_RADIUS)
  expedition.value = { path, index: 0 }
  redraw()
  expeditionTimer = window.setInterval(() => {
    const exp = expedition.value
    if (exp === null) return
    const nextIndex = exp.index + 1
    if (nextIndex >= exp.path.length) {
      const dest = exp.path[exp.path.length - 1]
      stopExpedition()
      arriveAt(dest)
      return
    }
    const p = exp.path[nextIndex]
    revealAt(p.x, p.y, SIGHT_RADIUS)
    exp.index = nextIndex
    redraw()
  }, tick)
}

const startExpedition = (): void => {
  const result = routeResult.value
  const end = routeEnd.value
  if (result === null || end === null || expedition.value !== null) return
  runExpedition(result.path)
}

const sendScout = (): void => {
  const preview = scoutPreview.value
  const target = scoutTarget.value
  if (preview === null || target === null || expedition.value !== null) return
  const { width, height } = world.value.config
  const probe = scoutProbeTarget(target, world.value.origin, SCOUT_PROBE, width, height)
  // The known leg stays on explored cells; the probe is the scout physically
  // entering the unknown and revealing it as it walks.
  const tail = findPath(world.value, target, probe)
  const path = tail === null ? preview.path : [...preview.path, ...tail.path.slice(1)]
  runExpedition(path)
}

const arriveAt = (point: Point): void => {
  const { width, height } = world.value.config
  revealAt(point.x, point.y, SIGHT_RADIUS)
  const vault = world.value.vaultSlots.find(v => v.x === point.x && v.y === point.y)
  const location = world.value.locations.find(l => l.x === point.x && l.y === point.y)
  const revealed = world.value.locations.filter(
    l => tileVisible(l.x, l.y) && !(expeditionKnownBefore?.has(l.id) ?? false),
  )
  for (const found of revealed) recordDiscovery(found)
  expeditionKnownBefore = null
  if (location !== undefined) {
    selectedLocation.value = location
    selectedVault.value = null
  } else if (vault !== undefined) {
    selectedVault.value = vault
    selectedLocation.value = null
  }
  redraw()
}

const toggleShowAll = (): void => {
  showAll.value = !showAll.value
  redraw()
}

const togglePlayerPreview = (): void => {
  playerPreview.value = !playerPreview.value
  redraw()
}

const toggleRoadDiscount = (): void => {
  roadDiscountEnabled.value = !roadDiscountEnabled.value
  recomputeRoute()
  redraw()
}

const toggleScoutMode = (): void => {
  scoutMode.value = !scoutMode.value
  if (!scoutMode.value) scoutTarget.value = null
  scoutHint.value = ''
  redraw()
}

const recordDiscovery = (loc: MapLocation): void => {
  if (discoveries.value.some(d => d.id === loc.id)) return
  discoveries.value = [loc, ...discoveries.value].slice(0, 12)
}

const toggleProdShow = (): void => {
  prodShow.value = !prodShow.value
  redraw()
}

const loadProdMap = async (): Promise<void> => {
  const id = prodVaultId.value.trim()
  if (id === '' || prodLoading.value) return
  if (!useAuthStore().isAuthenticated) {
    prodError.value = 'Log in via the app first (session token required), then retry.'
    return
  }
  prodLoading.value = true
  prodError.value = null
  try {
    const { unlocked, total, anchors } = await fetchProdMap(id)
    prodLocations.value = unlocked
    prodAnchors.value = anchors
    prodTotal.value = total
    prodShow.value = true
  } catch (err) {
    prodError.value = handleStoreError(err, 'Load production map', false)
    prodLocations.value = []
    prodAnchors.value = []
    prodTotal.value = 0
  } finally {
    prodLoading.value = false
    redraw()
  }
}

const applyPublicAnchors = (): void => {
  anchoredPreview.value = !anchoredPreview.value
  regenerate()
}

const toggleTerrainChanges = (): void => {
  showTerrainChanges.value = !showTerrainChanges.value
  redraw()
}

const clearProdMap = (): void => {
  prodVaultId.value = ''
  prodLocations.value = []
  prodAnchors.value = []
  prodTotal.value = 0
  prodError.value = null
  redraw()
}

const terrainCounts = computed(() => {
  const counts: Record<TerrainType, number> = { wasteland: 0, forest: 0, ruins: 0, hills: 0, water: 0 }
  for (const t of world.value.terrain) counts[t]++
  return counts
})

const hoveredTerrain = computed(() => {
  const tile = hoverTile.value
  if (tile === null) return null
  const idx = tile.y * world.value.config.width + tile.x
  return {
    x: tile.x,
    y: tile.y,
    terrain: world.value.terrain[idx],
    cost: world.value.travelCost[idx],
    known: tileVisible(tile.x, tile.y),
  }
})

const routeEndKnown = computed(() => {
  const end = routeEnd.value
  return end === null ? true : tileVisible(end.x, end.y)
})

const regionCells = computed(() => {
  const cells: Array<{ key: string; count: number }> = []
  for (let r = 0; r < 4; r++) {
    for (let c = 0; c < 4; c++) {
      const key = `r${r}c${c}`
      cells.push({ key, count: world.value.validation.valuableByRegion[key] ?? 0 })
    }
  }
  return cells
})

const pointLabel = (p: Point): string => `(${p.x}, ${p.y})`

/** Travel-time ETA from the world origin to the selected location, or null when unreachable. */
const selectedLocationEta = computed<{ hours: number } | null>(() => {
  const loc = selectedLocation.value
  if (loc === null || !tileVisible(loc.x, loc.y)) return null
  const result = findPath(world.value, world.value.origin, { x: loc.x, y: loc.y }, pathOptions())
  return result === null ? null : { hours: result.hours }
})

// ── Known-places list (non-mouse access path) ───────────────────────────
// The canvas is pointer-only; this list is how keyboard and touch users reach
// places. It only offers visible entries, per the visibility contract.

type KnownEntry =
  | { key: string; kind: 'vault'; label: string; sublabel: string; x: number; y: number; vault: VaultSlot }
  | { key: string; kind: 'location'; label: string; sublabel: string; x: number; y: number; location: MapLocation }

const knownEntries = computed<KnownEntry[]>(() => {
  const w = world.value
  const vaults: KnownEntry[] = w.vaultSlots
    .filter(v => tileVisible(v.x, v.y))
    .map(v => ({ key: `vault-${v.id}`, kind: 'vault', label: `Vault ${v.id}`, sublabel: 'vault slot', x: v.x, y: v.y, vault: v }))
  const locations: KnownEntry[] = w.locations
    .filter(l => tileVisible(l.x, l.y))
    .map(l => ({ key: `loc-${l.id}`, kind: 'location', label: l.name, sublabel: locationMeta(l.kind).label, x: l.x, y: l.y, location: l }))
  return [...vaults, ...locations]
})

const knownRowRefs: Record<string, HTMLButtonElement | null> = {}
const knownRowRefFns = new Map<string, (el: unknown) => void>()
const knownRowRef = (key: string): ((el: unknown) => void) => {
  let fn = knownRowRefFns.get(key)
  if (fn === undefined) {
    fn = (el: unknown) => {
      knownRowRefs[key] = el as HTMLButtonElement | null
    }
    knownRowRefFns.set(key, fn)
  }
  return fn
}

const isEntrySelected = (entry: KnownEntry): boolean =>
  entry.kind === 'vault'
    ? selectedVault.value?.id === entry.vault.id
    : selectedLocation.value?.id === entry.location.id

const selectEntry = (entry: KnownEntry): void => {
  stopExpedition()
  if (entry.kind === 'vault') {
    selectedVault.value = entry.vault
    selectedLocation.value = null
  } else {
    selectedLocation.value = entry.location
    selectedVault.value = null
  }
  if (routeStart.value === null) {
    routeStart.value = { x: entry.x, y: entry.y }
    routeEnd.value = null
    routeResult.value = null
    routeUnreachable.value = false
    routeUnknown.value = false
  } else {
    routeEnd.value = { x: entry.x, y: entry.y }
    recomputeRoute()
    routeUnknown.value = false
  }
  redraw()
}

const onKnownKeydown = (event: KeyboardEvent): void => {
  if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp' && event.key !== 'Home' && event.key !== 'End') return
  const keys = knownEntries.value.map(entry => entry.key)
  if (keys.length === 0) return
  event.preventDefault()
  const current = keys.findIndex(key => knownRowRefs[key] === document.activeElement)
  let next: string
  if (event.key === 'ArrowDown') next = keys[(current + 1) % keys.length]!
  else if (event.key === 'ArrowUp') next = keys[(current - 1 + keys.length) % keys.length]!
  else if (event.key === 'Home') next = keys[0]!
  else next = keys[keys.length - 1]!
  knownRowRefs[next]?.focus()
}

/** Clamp the Locations density input to the supported 10–600 range. */
const clampedLocationCount = (): number => {
  const raw = Number(locationCountInput.value)
  if (!Number.isFinite(raw) || raw <= 0) return DEFAULT_WORLD_CONFIG.locationCount
  return Math.min(600, Math.max(10, Math.round(raw)))
}



/**
 * Cached biome-blended grid buffer. When radius > 0, each cell's color is the
 * weighted average of its (2r+1)×(2r+1) neighborhood, computed as a separable
 * two-pass box blur in cell space over the raw pixel data. Edge cells clamp
 * their window to the grid bounds and divide by the actual sample count, so
 * the average stays exact — no edge darkening. The bilinear upscale in redraw()
 * then provides the sub-grid interpolation.
 */
const getBlendedBuffer = (radius: number): HTMLCanvasElement | null => {
  if (blendedBuffer !== null && blendedBufferRadius === radius) return blendedBuffer
  const w = world.value
  const { width, height } = w.config
  const buffer = document.createElement('canvas')
  buffer.width = width
  buffer.height = height
  const bctx = buffer.getContext('2d')
  if (bctx === null) return null

  const cellCount = width * height
  const src = new Float32Array(cellCount * 3)
  for (let i = 0; i < cellCount; i++) {
    const rgb = TERRAIN_RGB[w.terrain[i]]
    src[i * 3] = rgb[0]
    src[i * 3 + 1] = rgb[1]
    src[i * 3 + 2] = rgb[2]
  }

  // Horizontal pass — average each row over the clamped [x-r, x+r] window.
  const tmp = new Float32Array(cellCount * 3)
  for (let y = 0; y < height; y++) {
    const row = y * width
    for (let x = 0; x < width; x++) {
      const x0 = Math.max(0, x - radius)
      const x1 = Math.min(width - 1, x + radius)
      let r = 0
      let g = 0
      let b = 0
      for (let k = x0; k <= x1; k++) {
        const i = (row + k) * 3
        r += src[i]
        g += src[i + 1]
        b += src[i + 2]
      }
      const count = x1 - x0 + 1
      const i = (row + x) * 3
      tmp[i] = r / count
      tmp[i + 1] = g / count
      tmp[i + 2] = b / count
    }
  }

  // Vertical pass — same window over columns, then write rounded RGB.
  const image = bctx.createImageData(width, height)
  const data = image.data
  for (let y = 0; y < height; y++) {
    const y0 = Math.max(0, y - radius)
    const y1 = Math.min(height - 1, y + radius)
    for (let x = 0; x < width; x++) {
      let r = 0
      let g = 0
      let b = 0
      for (let k = y0; k <= y1; k++) {
        const i = (k * width + x) * 3
        r += tmp[i]
        g += tmp[i + 1]
        b += tmp[i + 2]
      }
      const count = y1 - y0 + 1
      const i = (y * width + x) * 4
      data[i] = Math.round(r / count)
      data[i + 1] = Math.round(g / count)
      data[i + 2] = Math.round(b / count)
      data[i + 3] = 255
    }
  }

  bctx.putImageData(image, 0, 0)
  blendedBuffer = buffer
  blendedBufferRadius = radius
  return buffer
}

const regenerate = (): void => {
  const seed = seedInput.value.trim()
  const config = {
    seed: seed === '' ? DEFAULT_WORLD_CONFIG.seed : seed,
    locationCount: clampedLocationCount(),
  }
  baseWorld.value = generateWorld(config)
  world.value = anchoredPreview.value ? generateWorld(config, fixtureAnchors.value) : baseWorld.value
  blendedBuffer = null
  blendedBufferRadius = -1
  claimedIds.value = []
  hoverTile.value = null
  routeStart.value = null
  routeEnd.value = null
  routeResult.value = null
  routeUnreachable.value = false
  discoveries.value = []
  resetFog()
  redraw()
}

const randomSeed = (): void => {
  // Explicit user action — the only place Math.random() is allowed.
  seedInput.value = Math.random().toString(36).slice(2)
  regenerate()
}

/** Locations density control — applied on `change`, never per keystroke. */
const applyLocationCount = (): void => {
  locationCountInput.value = String(clampedLocationCount())
  regenerate()
}

const toggleLayer = (key: LayerKey): void => {
  layers.value[key] = !layers.value[key]
  redraw()
}

const setBlendRadius = (event: Event): void => {
  const target = event.target as HTMLSelectElement
  blendRadius.value = Number(target.value)
  redraw()
}

const togglePlayerIcons = (): void => {
  playerIcons.value = !playerIcons.value
  redraw()
}

const toggleMinorCaches = (): void => {
  showMinorCaches.value = !showMinorCaches.value
  redraw()
}

const toggleClaim = (id: number): void => {
  const claimed = claimedIds.value.includes(id)
  claimedIds.value = claimed ? claimedIds.value.filter(v => v !== id) : [...claimedIds.value, id]
  if (!claimed) {
    const slot = world.value.vaultSlots.find(s => s.id === id)
    if (slot !== undefined) revealAt(slot.x, slot.y, CLAIM_REVEAL)
  }
  redraw()
}

const clearRoute = (): void => {
  stopExpedition()
  routeStart.value = null
  routeEnd.value = null
  routeResult.value = null
  routeUnreachable.value = false
  routeUnknown.value = false
  redraw()
}

const eventToTile = (event: MouseEvent): Point | null => {
  const canvas = canvasRef.value
  if (canvas === null) return null
  const rect = canvas.getBoundingClientRect()
  const px = ((event.clientX - rect.left) * canvas.width) / rect.width
  const py = ((event.clientY - rect.top) * canvas.height) / rect.height
  const x = Math.floor(px / TILE)
  const y = Math.floor(py / TILE)
  if (x < 0 || x >= world.value.config.width || y < 0 || y >= world.value.config.height) return null
  return { x, y }
}

const onMouseMove = (event: MouseEvent): void => {
  const tile = eventToTile(event)
  if (tile === null) return
  const prev = hoverTile.value
  if (prev !== null && prev.x === tile.x && prev.y === tile.y) return
  hoverTile.value = tile
  redraw()
}

const onMouseLeave = (): void => {
  if (hoverTile.value === null) return
  hoverTile.value = null
  redraw()
}

const onCanvasClick = (event: MouseEvent): void => {
  const tile = eventToTile(event)
  if (tile === null) return
  const { width, height } = world.value.config
  if (scoutMode.value) {
    if (!tileVisible(tile.x, tile.y)) {
      scoutHint.value = 'Only revealed tiles can be scouted.'
    } else if (!isFrontierTile(explored.value, width, height, tile.x, tile.y)) {
      scoutHint.value = 'Pick a revealed tile on the edge of the unknown.'
    } else {
      scoutTarget.value = tile
      scoutHint.value = ''
    }
    redraw()
    return
  }
  stopExpedition()
  const vault: VaultSlot | undefined = world.value.vaultSlots.find(v => v.x === tile.x && v.y === tile.y)
  if (vault !== undefined) {
    // Visibility contract: a hidden vault cannot become the selection or origin.
    if (!tileVisible(vault.x, vault.y)) return
    selectedLocation.value = null
    routeStart.value = { x: vault.x, y: vault.y }
    routeEnd.value = null
    routeResult.value = null
    routeUnreachable.value = false
    routeUnknown.value = false
    if (isExplored(explored.value, width, height, vault.x, vault.y)) selectedVault.value = vault
    else selectedVault.value = null
    redraw()
    return
  }
  const location: MapLocation | undefined = world.value.locations.find(l => l.x === tile.x && l.y === tile.y)
  const point = location !== undefined ? { x: location.x, y: location.y } : tile
  if (!tileVisible(point.x, point.y)) {
    // Unknown target: never select it; a preview must not reveal route geometry.
    if (routeStart.value !== null) {
      routeEnd.value = point
      routeResult.value = null
      routeUnreachable.value = false
      routeUnknown.value = true
      redraw()
    }
    return
  }
  if (location !== undefined) {
    selectedLocation.value = location
    selectedVault.value = null
  }
  if (routeStart.value === null) {
    routeStart.value = point
    routeEnd.value = null
    routeResult.value = null
    routeUnreachable.value = false
    routeUnknown.value = false
  } else {
    routeEnd.value = point
    // Known-only routing: in player mode the path may not cross unexplored cells.
    recomputeRoute()
    routeUnknown.value = false
  }
  redraw()
}

const redraw = (): void => {
  const canvas = canvasRef.value
  if (canvas === null) return
  const ctx = canvas.getContext('2d')
  if (ctx === null) return
  const w = world.value
  const { width, height } = w.config
  const layersOn = layers.value

  ctx.clearRect(0, 0, canvas.width, canvas.height)
  ctx.fillStyle = '#0f0e0d'
  ctx.fillRect(0, 0, canvas.width, canvas.height)

  if (layersOn.terrain) {
    const radius = blendRadius.value
    if (radius > 0) {
      // Biome blend: upscale the blended grid buffer with high-quality bilinear
      // smoothing — the sub-grid interpolation that turns cell gradients into
      // seamless terrain transitions. No blur() filter here; the blend itself
      // is the smoothing.
      const blended = getBlendedBuffer(radius)
      if (blended !== null) {
        ctx.imageSmoothingEnabled = true
        ctx.imageSmoothingQuality = 'high'
        ctx.filter = 'none'
        ctx.drawImage(blended, 0, 0, canvas.width, canvas.height)
      }
    } else {
      for (let y = 0; y < height; y++) {
        for (let x = 0; x < width; x++) {
          ctx.fillStyle = TERRAIN_META[w.terrain[y * width + x]].color
          ctx.fillRect(x * TILE, y * TILE, TILE, TILE)
        }
      }
      // Water as overlapping discs so rivers read smooth, not pixelated.
      ctx.fillStyle = TERRAIN_META.water.color
      const wr = TILE * 0.8
      for (let i = 0; i < width * height; i++) {
        if (w.terrain[i] !== 'water') continue
        if (visibilityEnforced.value && !tileVisible(i % width, Math.floor(i / width))) continue
        ctx.beginPath()
        ctx.arc((i % width) * TILE + TILE / 2, Math.floor(i / width) * TILE + TILE / 2, wr, 0, Math.PI * 2)
        ctx.fill()
      }
    }
  }

  if (layersOn.grid) {
    ctx.strokeStyle = 'rgba(0, 255, 0, 0.07)'
    ctx.lineWidth = 1
    ctx.beginPath()
    for (let x = 0; x <= width; x++) {
      ctx.moveTo(x * TILE + 0.5, 0)
      ctx.lineTo(x * TILE + 0.5, height * TILE)
    }
    for (let y = 0; y <= height; y++) {
      ctx.moveTo(0, y * TILE + 0.5)
      ctx.lineTo(width * TILE, y * TILE + 0.5)
    }
    ctx.stroke()
  }

  if (layersOn.roads) {
    ctx.lineJoin = 'round'
    ctx.lineCap = 'round'
    for (const edge of w.roads) {
      const pts = edge.path.map(p => ({ x: p.x * TILE + TILE / 2, y: p.y * TILE + TILE / 2 }))
      if (pts.length === 0) continue
      ctx.beginPath()
      const first = pts[0]
      ctx.moveTo(first.x, first.y)
      for (let i = 1; i < pts.length - 1; i++) {
        const mx = (pts[i].x + pts[i + 1].x) / 2
        const my = (pts[i].y + pts[i + 1].y) / 2
        ctx.quadraticCurveTo(pts[i].x, pts[i].y, mx, my)
      }
      const last = pts[pts.length - 1]
      ctx.lineTo(last.x, last.y)
      // Casing then fill, so roads stay crisp against textured terrain.
      ctx.lineWidth = 3
      ctx.strokeStyle = 'rgba(0, 0, 0, 0.6)'
      ctx.stroke()
      ctx.lineWidth = 1.5
      ctx.strokeStyle = '#b8a06a'
      ctx.stroke()
    }
  }

  if (layersOn.vaults) {
    for (const v of w.vaultSlots) {
      if (visibilityEnforced.value && !tileVisible(v.x, v.y)) continue
      const px = v.x * TILE + 1
      const py = v.y * TILE + 1
      const size = TILE - 2
      const claimed = claimedIds.value.includes(v.id)
      if (playerIcons.value) {
        drawVaultDoor(ctx, v.x * TILE + TILE / 2, v.y * TILE + TILE / 2, '#00ff00', claimed)
      } else {
        // Debug style — tiny squares, kept exactly as-is.
        ctx.strokeStyle = '#00ff00'
        ctx.lineWidth = 1
        if (claimed) {
          ctx.fillStyle = '#00ff00'
          ctx.fillRect(px, py, size, size)
        } else {
          ctx.strokeRect(px + 0.5, py + 0.5, size - 1, size - 1)
        }
      }
    }
  }

  if (layersOn.locations) {
    for (const loc of w.locations) {
      if (visibilityEnforced.value && !tileVisible(loc.x, loc.y)) continue
      if (!showMinorCaches.value && loc.kind === 'supply_cache') continue
      const cx = loc.x * TILE + TILE / 2
      const cy = loc.y * TILE + TILE / 2
      const { color, icon } = locationMeta(loc.kind)
      if (playerIcons.value) {
        icon(ctx, cx, cy, color)
      } else {
        // Debug style — small colored dots, kept exactly as-is.
        ctx.fillStyle = color
        ctx.beginPath()
        ctx.arc(cx, cy, 2.5, 0, Math.PI * 2)
        ctx.fill()
        ctx.strokeStyle = 'rgba(0, 0, 0, 0.7)'
        ctx.lineWidth = 1
        ctx.stroke()
      }
    }
  }

  if (layersOn.origin) {
    const ox = w.origin.x * TILE + TILE / 2
    const oy = w.origin.y * TILE + TILE / 2
    ctx.strokeStyle = '#00ff00'
    ctx.lineWidth = 1.5
    ctx.beginPath()
    ctx.arc(ox, oy, 4, 0, Math.PI * 2)
    ctx.stroke()
    ctx.fillStyle = '#00ff00'
    ctx.beginPath()
    ctx.arc(ox, oy, 2, 0, Math.PI * 2)
    ctx.fill()
  }

  if (layersOn.route && routeResult.value !== null) {
    const result = routeResult.value
    ctx.strokeStyle = '#00ff00'
    ctx.lineWidth = 2
    ctx.lineJoin = 'round'
    ctx.lineCap = 'round'
    ctx.beginPath()
    result.path.forEach((p, i) => {
      const px = p.x * TILE + TILE / 2
      const py = p.y * TILE + TILE / 2
      if (i === 0) ctx.moveTo(px, py)
      else ctx.lineTo(px, py)
    })
    ctx.stroke()
  }

  if (layersOn.route) {
    if (routeStart.value !== null) {
      const s = routeStart.value
      ctx.strokeStyle = '#00ff00'
      ctx.lineWidth = 1.5
      ctx.strokeRect(s.x * TILE + 1.5, s.y * TILE + 1.5, TILE - 3, TILE - 3)
    }
    if (routeEnd.value !== null) {
      const e = routeEnd.value
      ctx.fillStyle = routeUnreachable.value ? '#ff0000' : '#00ff00'
      ctx.fillRect(e.x * TILE + 2, e.y * TILE + 2, TILE - 4, TILE - 4)
    }
  }

  if (!showAll.value) {
    ctx.fillStyle = playerPreview.value ? '#040604' : 'rgba(2, 4, 2, 0.88)'
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        if (explored.value[y * width + x] === 1) continue
        ctx.fillRect(x * TILE, y * TILE, TILE, TILE)
      }
    }
  }
  if (expedition.value !== null) {
    const p = expedition.value.path[expedition.value.index]
    if (p !== undefined) {
      const dx = p.x * TILE + TILE / 2
      const dy = p.y * TILE + TILE / 2
      ctx.fillStyle = '#ffffff'
      ctx.beginPath()
      ctx.arc(dx, dy, 2.5, 0, Math.PI * 2)
      ctx.fill()
      ctx.strokeStyle = '#00ff00'
      ctx.lineWidth = 1.5
      ctx.beginPath()
      ctx.arc(dx, dy, 5, 0, Math.PI * 2)
      ctx.stroke()
    }
  }
  if (!playerPreview.value && anchoredPreview.value) {
    if (showTerrainChanges.value) {
      ctx.strokeStyle = '#ffb000'
      ctx.lineWidth = 1
      for (const idx of changedTiles.value) {
        ctx.strokeRect((idx % width) * TILE, Math.floor(idx / width) * TILE, TILE, TILE)
      }
    }
    for (const d of w.anchorDiagnostics) {
      if (d.before === null) continue
      const px = registryToCanvas(d.anchor.coord_x, width * TILE)
      const py = registryToCanvas(d.anchor.coord_y, height * TILE)
      ctx.strokeStyle = d.conflict ? '#ff5555' : '#ffffff'
      ctx.lineWidth = 2
      ctx.beginPath()
      ctx.moveTo(px - 5, py)
      ctx.lineTo(px + 5, py)
      ctx.moveTo(px, py - 5)
      ctx.lineTo(px, py + 5)
      ctx.stroke()
    }
  }
  if (!playerPreview.value && prodShow.value && prodLocations.value.length > 0) {
    ctx.strokeStyle = '#ffb000'
    ctx.lineWidth = 1.5
    for (const l of prodLocations.value) {
      const px = registryToCanvas(l.coord_x)
      const py = registryToCanvas(l.coord_y)
      ctx.beginPath()
      ctx.moveTo(px, py - 6)
      ctx.lineTo(px + 6, py)
      ctx.lineTo(px, py + 6)
      ctx.lineTo(px - 6, py)
      ctx.closePath()
      ctx.stroke()
    }
  }
  if (hoverTile.value !== null) {
    const h = hoverTile.value
    ctx.fillStyle = 'rgba(0, 255, 0, 0.15)'
    ctx.fillRect(h.x * TILE, h.y * TILE, TILE, TILE)
  }

  // Labels: home and selection always, hover on demand (contract DD6). Drawn last
  // so they sit above fog and markers.
  ctx.font = '9px ui-monospace, monospace'
  ctx.textBaseline = 'middle'
  const drawLabel = (x: number, y: number, text: string, color: string): void => {
    const px = x * TILE + TILE / 2
    const py = y * TILE + TILE / 2 - TILE
    ctx.lineWidth = 3
    ctx.strokeStyle = 'rgba(0, 0, 0, 0.85)'
    ctx.strokeText(text, px + 0.5, py)
    ctx.fillStyle = color
    ctx.fillText(text, px + 0.5, py)
  }
  drawLabel(w.origin.x, w.origin.y, 'HOME', '#7cff9b')
  const sel = selectedLocation.value
  if (sel !== null && (!visibilityEnforced.value || tileVisible(sel.x, sel.y))) {
    drawLabel(sel.x, sel.y, sel.name, '#eaffea')
  }
  const hov = hoverTile.value
  if (hov !== null && (!visibilityEnforced.value || tileVisible(hov.x, hov.y))) {
    drawLabel(hov.x, hov.y, `${hov.x},${hov.y}`, '#9effb0')
  }
}

onMounted(() => {
  const canvas = canvasRef.value
  if (canvas !== null) {
    canvas.width = TILE * DEFAULT_WORLD_CONFIG.width
    canvas.height = TILE * DEFAULT_WORLD_CONFIG.height
  }
  blendedBuffer = null
  blendedBufferRadius = -1
  resetFog()
  redraw()
})

onUnmounted(() => {
  stopExpedition()
})
</script>

<template>
  <div class="mx-auto max-w-7xl px-6 py-8">
    <header class="panel-header">
      <div>
        <h1 class="flicker text-2xl font-bold terminal-glow text-theme-primary">OVERWORLD MAP GENERATOR</h1>
        <p class="mt-1 text-sm text-theme-primary/60">
          Dev-only prototype — tune the generator, inspect validation, test A* routing.
        </p>
      </div>
      <div v-if="!playerPreview" class="flex flex-wrap items-center gap-2">
        <Input v-model="seedInput" class="w-44 font-mono" placeholder="seed" />
        <label class="flex items-center gap-1.5 text-xs text-theme-primary/70">
          Locations
          <input
            v-model="locationCountInput"
            type="number"
            min="10"
            max="600"
            step="10"
            class="h-9 w-24 rounded-md border border-input bg-transparent px-2.5 py-1 font-mono text-sm text-theme-primary outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
            @change="applyLocationCount"
          />
        </label>
        <Button variant="outline" @click="randomSeed">Random seed</Button>
        <Button @click="regenerate">Regenerate</Button>
      </div>
      <label class="flex cursor-pointer items-center gap-2 text-sm text-theme-primary/80">
        <input
          type="checkbox"
          class="accent-theme-primary"
          :checked="playerPreview"
          @change="togglePlayerPreview"
        />
        Player preview
      </label>
    </header>

    <div class="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
      <section aria-label="World map">
        <div class="crt-screen w-fit border border-theme-primary/30 bg-surface-sunken p-2">
          <canvas
            ref="canvasRef"
            class="block h-auto w-full max-w-[640px] cursor-crosshair"
            aria-label="Generated overworld map"
            @mousemove="onMouseMove"
            @mouseleave="onMouseLeave"
            @click="onCanvasClick"
          />
        </div>

        <div class="mt-4 grid gap-4 sm:grid-cols-2">
          <div class="rounded border border-theme-primary/20 bg-surface p-3">
            <h2 class="mb-2 text-xs font-bold tracking-widest text-theme-primary/70">TERRAIN</h2>
            <ul class="flex flex-col gap-1 text-xs text-theme-primary/80">
              <li v-for="entry in TERRAIN_LEGEND" :key="entry.type" class="flex items-center gap-2">
                <span class="inline-block h-3 w-3 border border-black/40" :class="entry.swatch" />
                <span class="capitalize">{{ entry.type }}</span>
                <span class="ml-auto text-theme-primary/50">cost {{ entry.cost }}</span>
              </li>
            </ul>
            <p class="mt-2 text-[10px] text-theme-primary/40">hours = cost × {{ HOURS_PER_COST }}</p>
          </div>
          <div class="rounded border border-theme-primary/20 bg-surface p-3">
            <h2 class="mb-2 text-xs font-bold tracking-widest text-theme-primary/70">LOCATIONS</h2>
            <ul class="grid grid-cols-2 gap-1 text-xs text-theme-primary/80">
              <li v-for="entry in LOCATION_LEGEND" :key="entry.kind" class="flex items-center gap-2">
                <span class="inline-block h-3 w-3 border border-black/40" :class="entry.swatch" />
                <span>{{ entry.label }}</span>
              </li>
            </ul>
          </div>
        </div>
      </section>

      <aside class="flex flex-col gap-4">
        <Card>
          <CardHeader>
            <CardTitle class="text-sm">LAYERS</CardTitle>
          </CardHeader>
          <CardContent class="grid grid-cols-2 gap-2 text-sm">
            <label
              v-for="toggle in LAYER_TOGGLES"
              :key="toggle.key"
              class="flex cursor-pointer items-center gap-2 text-theme-primary/80"
            >
              <input
                type="checkbox"
                class="accent-theme-primary"
                :checked="layers[toggle.key]"
                @change="toggleLayer(toggle.key)"
              />
              {{ toggle.label }}
            </label>

            <label
              class="col-span-2 mt-1 flex items-center justify-between gap-2 text-theme-primary/80"
            >
              <span>Biome blend</span>
              <select
                :value="blendRadius"
                class="h-8 w-24 cursor-pointer rounded-md border border-input bg-transparent px-2 font-mono text-xs text-theme-primary outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
                aria-label="Biome blend radius"
                @change="setBlendRadius"
              >
                <option v-for="option in BLEND_OPTIONS" :key="option.radius" :value="option.radius">
                  {{ option.label }}
                </option>
              </select>
            </label>
            <label
              class="col-span-2 mt-1 flex cursor-pointer items-center gap-2 text-theme-primary/80"
            >
              <input
                type="checkbox"
                class="accent-theme-primary"
                :checked="playerIcons"
                @change="togglePlayerIcons"
              />
              Player icons
            </label>
            <label
              v-if="!playerPreview"
              class="col-span-2 mt-1 flex cursor-pointer items-center gap-2 text-theme-primary/80"
            >
              <input
                type="checkbox"
                class="accent-theme-primary"
                :checked="roadDiscountEnabled"
                @change="toggleRoadDiscount"
              />
              Road discount (experiment)
            </label>
            <label
              v-if="!playerPreview"
              class="col-span-2 mt-1 flex cursor-pointer items-center gap-2 text-theme-primary/80"
            >
              <input
                type="checkbox"
                class="accent-theme-primary"
                :checked="showMinorCaches"
                @change="toggleMinorCaches"
              />
              Minor caches (density)
            </label>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle class="text-sm">TERRAIN COUNTS</CardTitle>
          </CardHeader>
          <CardContent class="flex flex-col gap-1 text-sm">
            <p v-for="entry in TERRAIN_LEGEND" :key="entry.type" class="flex justify-between text-theme-primary/80">
              <span class="capitalize">{{ entry.type }}</span>
              <span class="text-theme-primary">{{ terrainCounts[entry.type] }}</span>
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle class="text-sm">VALIDATION</CardTitle>
          </CardHeader>
          <CardContent class="flex flex-col gap-2 text-sm">
            <p class="flex justify-between text-theme-primary/80">
              <span>Reachable vaults</span>
              <span class="text-theme-primary">
                {{ world.validation.reachableVaults }} / {{ world.validation.totalVaults }}
              </span>
            </p>
            <p class="flex justify-between text-theme-primary/80">
              <span>Vaults w/ nearby scavenge</span>
              <span class="text-theme-primary">{{ world.validation.vaultsWithNearbyScavenge }}</span>
            </p>
            <p class="flex justify-between text-theme-primary/80">
              <span>Isolated regions</span>
              <span class="text-theme-primary">{{ world.validation.isolatedRegions }}</span>
            </p>
            <div>
              <p class="mb-1 text-xs text-theme-primary/50">VALUABLE SITES BY REGION (4×4)</p>
              <div class="grid grid-cols-4 gap-1">
                <span
                  v-for="cell in regionCells"
                  :key="cell.key"
                  class="bg-surface-raised px-1 py-0.5 text-center text-xs text-theme-primary"
                  :title="cell.key"
                >
                  {{ cell.count }}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle class="text-sm">READOUT</CardTitle>
          </CardHeader>
          <CardContent class="flex flex-col gap-3 text-sm">
            <div>
              <p class="text-xs text-theme-primary/50">HOVER</p>
              <p v-if="hoveredTerrain !== null && hoveredTerrain.known" class="text-theme-primary">
                ({{ hoveredTerrain.x }}, {{ hoveredTerrain.y }}) — {{ hoveredTerrain.terrain }} ·
                cost {{ costLabel(hoveredTerrain.cost) }}
              </p>
              <p v-else-if="hoveredTerrain !== null" class="text-theme-primary/40">
                ({{ hoveredTerrain.x }}, {{ hoveredTerrain.y }}) — unknown
              </p>
              <p v-else class="text-theme-primary/40">—</p>
            </div>
            <div>
              <p class="text-xs text-theme-primary/50">ROUTE</p>
              <p v-if="routeStart !== null" class="text-theme-primary">start {{ pointLabel(routeStart) }}</p>
              <p v-if="routeEnd !== null && routeResult !== null" class="text-theme-primary">
                → {{ pointLabel(routeEnd) }} · cost {{ routeResult.cost.toFixed(1) }} · {{ routeResult.hours }} h
              </p>
              <p v-if="routeEnd !== null && routeUnreachable" class="text-danger">
                → {{ pointLabel(routeEnd) }} · unreachable
              </p>
              <p v-if="routeStart === null" class="text-theme-primary/40">click a vault or location to start</p>
              <p v-if="routeEnd !== null && !routeEndKnown && !playerPreview" class="text-theme-primary/40">
                unexplored — send an expedition to discover
              </p>
              <p v-if="routeUnknown" class="text-danger">
                No known route
              </p>
              <Button
                v-if="routeEnd !== null && routeResult !== null && expedition === null"
                variant="outline"
                size="sm"
                class="mt-2"
                @click="startExpedition"
              >
                Send expedition
              </Button>
              <Button
                v-if="expedition !== null"
                variant="outline"
                size="sm"
                class="mt-2"
                @click="cancelExpedition"
              >
                Cancel expedition
              </Button>
              <p v-if="expedition !== null" class="text-theme-primary/80">
                Dweller en route… {{ expedition.index + 1 }}/{{ expedition.path.length }}
              </p>
            </div>
            <div>
              <p class="text-xs text-theme-primary/50">VAULT</p>
              <p v-if="selectedVault !== null" class="text-theme-primary">
                Vault {{ selectedVault.id }} — ({{ selectedVault.x }}, {{ selectedVault.y }}) · sector
                {{ selectedVault.sectorCol }},{{ selectedVault.sectorRow }}
              </p>
              <p v-else class="text-theme-primary/40">click a vault slot</p>
              <Button
                v-if="selectedVault !== null"
                variant="outline"
                size="sm"
                class="mt-2"
                @click="toggleClaim(selectedVault.id)"
              >
                {{ claimedIds.includes(selectedVault.id) ? 'Unclaim' : 'Claim' }}
              </Button>
            </div>
            <div>
              <p class="text-xs text-theme-primary/50">LOCATION</p>
              <p v-if="selectedLocation !== null" class="text-theme-primary">
                {{ selectedLocation.name }} — {{ locationMeta(selectedLocation.kind).label }} ({{ selectedLocation.x }},
                {{ selectedLocation.y }})
              </p>
              <p v-if="selectedLocation !== null" class="text-theme-primary/80">
                <template v-if="selectedLocationEta !== null">ETA {{ selectedLocationEta.hours }} h from origin</template>
                <span v-else class="text-danger">unreachable from origin</span>
              </p>
              <p v-else class="text-theme-primary/40">click a marker</p>
            </div>
            <div v-if="!playerPreview">
              <p class="text-xs text-theme-primary/50">FOG</p>
              <label class="mt-1 flex cursor-pointer items-center gap-2 text-theme-primary/80">
                <input
                  type="checkbox"
                  class="accent-theme-primary"
                  :checked="showAll"
                  @change="toggleShowAll"
                />
                Show all (debug)
              </label>
              <Button variant="outline" size="sm" class="mt-2" @click="resetFog">
                Reset fog
              </Button>
            </div>
            <Button v-if="routeStart !== null || routeEnd !== null" variant="outline" size="sm" @click="clearRoute">
              Clear route
            </Button>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle class="text-sm">SCOUT FRONTIER</CardTitle>
          </CardHeader>
          <CardContent class="flex flex-col gap-2 text-sm">
            <Button variant="outline" size="sm" @click="toggleScoutMode">
              {{ scoutMode ? 'Cancel scouting' : 'Scout this frontier' }}
            </Button>
            <p class="text-xs text-theme-primary/60">
              Pick a revealed tile on the edge of the unknown. The destination stays
              unknown — only a coarse duration is shown.
            </p>
            <template v-if="scoutTarget !== null">
              <p class="text-theme-primary">
                Frontier {{ pointLabel(scoutTarget) }}
                <span v-if="scoutPreview !== null">
                  · ETA ~{{ scoutPreview.band.low }}–{{ scoutPreview.band.high }} h
                </span>
                <span v-else class="text-danger"> · unreachable</span>
              </p>
              <Button
                v-if="scoutPreview !== null"
                size="sm"
                :disabled="expedition !== null"
                @click="sendScout"
              >
                Send scout
              </Button>
            </template>
            <p v-else-if="scoutHint !== ''" class="text-danger">{{ scoutHint }}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle class="text-sm">DISCOVERIES ({{ discoveries.length }})</CardTitle>
          </CardHeader>
          <CardContent>
            <p v-if="discoveries.length === 0" class="text-xs text-theme-primary/40">Nothing discovered yet.</p>
            <ul v-else class="flex max-h-40 flex-col gap-1 overflow-y-auto text-xs text-theme-primary/80">
              <li v-for="d in discoveries" :key="d.id" class="flex justify-between gap-2">
                <span class="truncate">{{ d.name }}</span>
                <span class="shrink-0 text-theme-primary/50">{{ locationMeta(d.kind).label }}</span>
              </li>
            </ul>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle class="text-sm">KNOWN PLACES ({{ knownEntries.length }})</CardTitle>
          </CardHeader>
          <CardContent>
            <p v-if="knownEntries.length === 0" class="text-xs text-theme-primary/40">Nothing discovered yet.</p>
            <ul v-else class="flex max-h-56 flex-col gap-1 overflow-y-auto" aria-label="Known places" @keydown="onKnownKeydown">
              <li v-for="entry in knownEntries" :key="entry.key">
                <button
                  :ref="knownRowRef(entry.key)"
                  type="button"
                  class="flex w-full items-center justify-between gap-2 rounded border border-transparent px-2 py-1 text-left text-xs text-theme-primary/80 hover:border-theme-primary/30 focus-visible:border-theme-primary/60"
                  :class="{ 'border-theme-primary/60 text-theme-primary': isEntrySelected(entry) }"
                  @click="selectEntry(entry)"
                >
                  <span class="truncate">{{ entry.label }}</span>
                  <span class="shrink-0 text-theme-primary/50">{{ entry.sublabel }}</span>
                </button>
              </li>
            </ul>
          </CardContent>
        </Card>
        <Card v-if="!playerPreview">
          <CardHeader>
            <CardTitle class="text-sm">OPTION A · SYNTHETIC SHARED FIXTURES</CardTitle>
          </CardHeader>
          <CardContent class="flex flex-col gap-2 text-xs text-theme-primary/80">
            <p>DEV-only experiment · no production anchors. White/red crosses preserve exact registry coordinates; roads connect projected cells.</p>
            <p>Seed {{ world.config.seed }} · generator v{{ world.config.version }} · constraint v{{ ANCHOR_CONSTRAINT_VERSION }} · {{ SHARED_FIXTURE_VERSION }} · {{ fixtureScenario }}</p>
            <label class="flex flex-col gap-1">
              Fixture scenario (resets local simulation)
              <select v-model="fixtureScenario" class="bg-surface border border-theme-primary/30 p-1" @change="regenerate">
                <option value="compatible">Three compatible anchors</option>
                <option value="conflict">Include co-cell conflict</option>
              </select>
            </label>
            <Button variant="outline" size="sm" @click="applyPublicAnchors">
              {{ anchoredPreview ? 'View base terrain' : 'Apply shared fixture anchors (A)' }}
            </Button>
            <label class="flex items-center gap-2">
              <input type="checkbox" :checked="showTerrainChanges" @change="toggleTerrainChanges" />
              Highlight final terrain changes (amber)
            </label>
            <p>{{ changedTiles.length }} final tiles differ from same-seed base · {{ world.anchorDiagnostics.filter(d => d.conflict).length }} conflicts</p>
            <ul class="flex flex-col gap-2" aria-label="Anchor diagnostics">
              <li v-for="d in world.anchorDiagnostics" :key="d.anchor.id">
                {{ d.anchor.name }} · exact ({{ d.anchor.coord_x }}, {{ d.anchor.coord_y }}) → cell ({{ d.x }}, {{ d.y }})
                <br />{{ d.before }} → {{ d.after }} · requested {{ d.anchor.terrain }} · {{ d.reachable ? 'reachable' : 'unreachable' }}
                <p v-if="d.conflict" class="text-danger">{{ d.conflict }}</p>
              </li>
            </ul>
            <p>Comparison includes downstream placement/road/repair effects, not only directly constrained cells. Switching modes resets claims, fog, routes, and the mock expedition.</p>
          </CardContent>
        </Card>
        <Card v-if="!playerPreview">
          <CardHeader>
            <CardTitle class="text-sm">PRODUCTION DATA (read-only)</CardTitle>
          </CardHeader>
          <CardContent class="flex flex-col gap-2 text-sm">
            <div class="flex flex-wrap items-center gap-2">
              <label class="flex items-center gap-1.5 text-xs text-theme-primary/70">
                Vault
                <Input v-model="prodVaultId" class="w-44 font-mono" placeholder="vault id" />
              </label>
              <Button variant="outline" size="sm" :disabled="prodVaultId.trim() === '' || prodLoading" @click="loadProdMap">
                {{ prodLoading ? 'Loading…' : 'Load' }}
              </Button>
              <Button v-if="prodLocations.length > 0 || prodError !== null" variant="ghost" size="sm" @click="clearProdMap">
                Clear
              </Button>
            </div>
            <label class="flex cursor-pointer items-center gap-2 text-theme-primary/80">
              <input
                type="checkbox"
                class="accent-theme-primary"
                :checked="prodShow"
                @change="toggleProdShow"
              />
              Production overlay
            </label>
            <p v-if="prodError !== null" class="text-danger">{{ prodError }}</p>
            <p v-else-if="prodLocations.length > 0" class="text-theme-primary/80">
              {{ prodLocations.length }} unlocked of {{ prodTotal }} received · independent of seed
            </p>
            <p v-else class="text-theme-primary/40">Enter your vault id, then Load. Requires app login (session token).</p>
            <p v-if="prodAnchors.length > 0" class="text-theme-primary/70">
              {{ prodAnchors.length }} registry vault signals received · scaled/rounded wire coordinates; not used for terrain
            </p>

            <ul v-if="prodLocations.length > 0" class="flex max-h-40 flex-col gap-1 overflow-y-auto text-xs text-theme-primary/80">
              <li v-for="l in prodLocations" :key="l.id" class="flex justify-between gap-2">
                <span>{{ l.name }}</span>
                <span class="text-theme-primary/50">{{ l.type }}</span>
              </li>
            </ul>
          </CardContent>
        </Card>
      </aside>
    </div>
  </div>
</template>
