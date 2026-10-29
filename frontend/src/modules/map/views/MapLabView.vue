<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import { Switch } from '@/core/components/ui/switch'
import { getErrorMessage } from '@/core/utils/errorHandler'
import AtlasTerrain from '../components/AtlasTerrain.vue'
import RegionOverlay from '../components/RegionOverlay.vue'
import { previewLocations } from '../dev/mapPreview'
import { getWorldPreview } from '../services/mapLabService'
import { MAP_UNITS, UNITS_PER_TILE } from '../utils/atlasProjection'
import type { WorldSnapshotRead } from '../models/map'

interface RegionValidation {
  tiles: number
  terrain: Record<string, number>
  in_main_component: number
}

interface RegionStat {
  id: string
  name: string
  danger_tier: number
  center_x: number
  center_y: number
  colorClass: string
  tiles: number
  terrain: Record<string, number>
  in_main_component: number
}

const REGION_CLASSES = [
  'bg-region-green-belt',
  'bg-region-rust-basin',
  'bg-region-broken-highlands',
  'bg-region-mirelands',
] as const

const seed = ref('wasteland-atlas-v1')
const world = ref<WorldSnapshotRead | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

const layers = ref({
  terrain: true,
  regions: true,
  slots: true,
  roads: true,
  anchors: false,
  locations: true,
  grid: false,
  origin: true,
})

const wire = (registry: number): number => (registry / 100) * MAP_UNITS

const terrainCounts = computed(() => {
  const counts = new Map<string, number>()
  for (const terrain of world.value?.terrain ?? []) {
    counts.set(terrain, (counts.get(terrain) ?? 0) + 1)
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1])
})

const regionStats = computed<RegionStat[]>(() => {
  const current = world.value
  if (current === null) return []
  const validation = (current.validation ?? {}) as {
    regions?: Record<string, RegionValidation>
  }
  return (current.regions ?? []).map((region, index) => {
    const stats = validation.regions?.[String(region.id)]
    return {
      id: String(region.id),
      name: String(region.name),
      danger_tier: Number(region.danger_tier ?? 0),
      center_x: Number(region.center_x ?? 0),
      center_y: Number(region.center_y ?? 0),
      colorClass: REGION_CLASSES[index] ?? 'bg-theme-primary',
      tiles: stats?.tiles ?? 0,
      terrain: stats?.terrain ?? {},
      in_main_component: stats?.in_main_component ?? 0,
    }
  })
})

const validation = computed(() => {
  const raw = (world.value?.validation ?? {}) as {
    isolated_regions?: string[]
    slot_tiles?: number
    reachable_slot_tiles?: number
    roads?: {
      slots_with_road?: number
      max_slot_road_distance?: number
      coverage_within_5?: number
      highway_components?: number
      hub_degrees?: Record<string, number>
    }
  }
  const roads = raw.roads ?? {}
  return {
    isolated: raw.isolated_regions ?? [],
    slotTiles: raw.slot_tiles ?? 0,
    reachableSlots: raw.reachable_slot_tiles ?? 0,
    slotsWithRoad: roads.slots_with_road ?? 0,
    maxSlotDistance: roads.max_slot_road_distance ?? 0,
    coverage: roads.coverage_within_5 ?? 0,
    highwayComponents: roads.highway_components ?? 0,
    minHubDegree: Math.min(...Object.values(roads.hub_degrees ?? { 0: 0 })),
  }
})

const slotPoints = computed(() =>
  (world.value?.slots ?? []).map((slot) => ({
    key: slot.slot_index,
    x: wire(slot.coord_x),
    y: wire(slot.coord_y),
  }))
)

const placePoints = computed(() =>
  previewLocations.map((location) => ({
    key: location.id,
    label: location.name,
    x: location.coord_x,
    y: location.coord_y,
  }))
)

const origin = computed(() => placePoints.value[0] ?? null)

const anchorPoints = computed(() => {
  const current = world.value
  if (current === null) return []
  return (current.road_anchors ?? []).map((anchor) => ({
    key: String(anchor.id ?? `${anchor.tile_x}:${anchor.tile_y}`),
    x: (Number(anchor.tile_x) + 0.5) * UNITS_PER_TILE,
    y: (Number(anchor.tile_y) + 0.5) * UNITS_PER_TILE,
  }))
})

const highwayCount = computed(
  () => (world.value?.road_edges ?? []).filter((edge) => edge.class === 'highway').length
)
const countryCount = computed(
  () => (world.value?.road_edges ?? []).filter((edge) => edge.class === 'country').length
)
const townCount = computed(
  () => (world.value?.road_edges ?? []).filter((edge) => edge.class === 'town').length
)
const accessCount = computed(
  () => (world.value?.road_edges ?? []).filter((edge) => edge.class === 'access').length
)

const gridLines = computed(() =>
  Array.from({ length: (world.value?.width ?? 80) + 1 }, (_, index) => index * UNITS_PER_TILE)
)

async function regenerate(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    world.value = await getWorldPreview(seed.value.trim() || 'wasteland-atlas-v1')
  } catch (caught) {
    world.value = null
    error.value = getErrorMessage(caught)
  } finally {
    loading.value = false
  }
}

function randomizeSeed(): void {
  seed.value = Math.random().toString(36).slice(2, 10)
  void regenerate()
}

onMounted(() => {
  void regenerate()
})
</script>

<template>
  <div class="mx-auto max-w-[1500px] space-y-6 px-4 py-8 font-mono sm:px-8">
    <header class="space-y-3">
      <RouterLink
        to="/dev"
        class="inline-flex items-center gap-2 text-xs text-theme-primary/70 underline-offset-4 hover:underline"
      >
        <Icon icon="mdi:arrow-left" class="size-4" /> Development tools
      </RouterLink>
      <div class="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p class="mb-1 text-[10px] uppercase tracking-[0.3em] text-theme-primary/60">
            World generation v3
          </p>
          <h1 class="text-2xl font-bold uppercase tracking-tight text-theme-primary sm:text-3xl">
            World map lab
          </h1>
        </div>
        <p class="max-w-md text-xs leading-relaxed text-theme-primary/60">
          Ephemeral preview: generate a v3 world, inspect regions and masks, and read the
          reachability report. Nothing here is persisted or served to players.
        </p>
      </div>
    </header>

    <section class="flex flex-wrap items-end gap-3 rounded-lg border border-theme-primary/25 bg-surface p-4">
      <label class="flex flex-col gap-1 text-[10px] uppercase tracking-widest text-theme-primary/60">
        Seed
        <input
          v-model="seed"
          class="w-56 rounded border border-theme-primary/30 bg-transparent px-3 py-2 text-sm text-theme-primary outline-none focus:border-theme-primary"
          aria-label="World seed"
          @keyup.enter="regenerate"
        />
      </label>
      <Button variant="ghost" size="sm" :disabled="loading" @click="randomizeSeed">
        Random seed
      </Button>
      <Button size="sm" :disabled="loading" @click="regenerate">
        {{ loading ? 'Generating…' : 'Regenerate' }}
      </Button>
      <p v-if="world" class="ml-auto text-[10px] leading-relaxed text-theme-primary/55">
        v{{ world.generator_version }} · {{ world.width }}×{{ world.height }} ·
        {{ world.recipe_fingerprint.slice(0, 12) }} ·
        {{ world.snapshot_checksum.slice(0, 12) }}
      </p>
    </section>

    <p v-if="error" class="text-xs text-status-fighting" role="status">
      Generation failed: {{ error }}
    </p>

    <div class="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
      <section
        class="relative overflow-hidden rounded-lg border border-theme-primary/30 bg-surface-canvas p-2"
        aria-label="Generated world map"
      >
        <svg
          v-if="world"
          :viewBox="`0 0 ${MAP_UNITS} ${MAP_UNITS}`"
          class="block aspect-square w-full"
          role="img"
          aria-label="Generated world map preview"
        >
          <AtlasTerrain
            v-if="layers.terrain"
            :snapshot="world"
            :roads="layers.roads ? world.roads : []"
            :rivers="world.rivers"
            :road-edges="layers.roads ? (world.road_edges ?? []) : []"
          />
          <RegionOverlay
            v-if="layers.regions"
            :region-map="world.region_map ?? []"
            :width="world.width"
            :height="world.height"
            :visible="layers.regions"
          />

          <g v-if="layers.grid" class="lab-grid" aria-hidden="true" pointer-events="none">
            <line
              v-for="line in gridLines"
              :key="`v-${line}`"
              :x1="line"
              y1="0"
              :x2="line"
              :y2="MAP_UNITS"
            />
            <line
              v-for="line in gridLines"
              :key="`h-${line}`"
              x1="0"
              :y1="line"
              :x2="MAP_UNITS"
              :y2="line"
            />
          </g>

          <g v-if="layers.slots" class="lab-slots" aria-hidden="true" pointer-events="none">
            <circle
              v-for="slot in slotPoints"
              :key="slot.key"
              :cx="slot.x"
              :cy="slot.y"
              r="0.9"
            />
          </g>

          <g v-if="layers.anchors" class="lab-anchors" aria-hidden="true" pointer-events="none">
            <rect
              v-for="anchor in anchorPoints"
              :key="anchor.key"
              :x="anchor.x - 1.1"
              :y="anchor.y - 1.1"
              width="2.2"
              height="2.2"
            />
          </g>

          <g v-if="layers.locations" class="lab-places" pointer-events="none">
            <g v-for="place in placePoints" :key="place.key">
              <circle :cx="place.x" :cy="place.y" r="2.2" />
              <title>{{ place.label }}</title>
            </g>
          </g>

          <g v-if="layers.origin && origin" class="lab-origin" pointer-events="none">
            <circle :cx="origin.x" :cy="origin.y" r="4.2" />
            <circle :cx="origin.x" :cy="origin.y" r="1.4" />
          </g>

          <g v-if="layers.regions" class="lab-region-labels" aria-hidden="true" pointer-events="none">
            <text
              v-for="region in regionStats"
              :key="region.id"
              :x="wire(region.center_x)"
              :y="wire(region.center_y)"
              text-anchor="middle"
            >
              {{ region.name }}
            </text>
          </g>
        </svg>
        <p v-else class="flex aspect-square items-center justify-center text-sm text-theme-primary/60">
          {{ loading ? 'Generating world…' : 'No world generated.' }}
        </p>
      </section>

      <aside class="space-y-4">
        <section class="rounded-lg border border-theme-primary/25 bg-surface p-4">
          <h2 class="mb-3 text-xs font-bold uppercase tracking-[0.2em] text-theme-primary">
            Layers
          </h2>
          <div class="grid grid-cols-2 gap-x-3 gap-y-2 text-xs text-theme-primary/80">
            <label class="flex items-center gap-2"><Switch v-model:checked="layers.terrain" />Terrain</label>
            <label class="flex items-center gap-2"><Switch v-model:checked="layers.regions" />Regions</label>
            <label class="flex items-center gap-2"><Switch v-model:checked="layers.slots" />Vault slots</label>
            <label class="flex items-center gap-2"><Switch v-model:checked="layers.roads" />Roads</label>
            <label class="flex items-center gap-2"><Switch v-model:checked="layers.anchors" />Anchors</label>
            <label class="flex items-center gap-2"><Switch v-model:checked="layers.locations" />Fixture places</label>
            <label class="flex items-center gap-2"><Switch v-model:checked="layers.grid" />Grid</label>
            <label class="flex items-center gap-2"><Switch v-model:checked="layers.origin" />Origin</label>
          </div>
        </section>

        <section class="rounded-lg border border-theme-primary/25 bg-surface p-4">
          <h2 class="mb-3 text-xs font-bold uppercase tracking-[0.2em] text-theme-primary">
            Counts
          </h2>
          <ul class="space-y-1 text-xs text-theme-primary/80">
            <li v-for="[terrain, count] in terrainCounts" :key="terrain" class="flex justify-between gap-3">
              <span class="capitalize">{{ terrain }}</span><span>{{ count }}</span>
            </li>
            <li class="flex justify-between gap-3 border-t border-theme-primary/15 pt-2">
              <span>Vault slots</span><span>{{ world?.slots.length ?? 0 }}</span>
            </li>
            <li class="flex justify-between gap-3">
              <span>Road tiles</span><span>{{ world?.roads.length ?? 0 }}</span>
            </li>
            <li class="flex justify-between gap-3">
              <span>Road anchors</span><span>{{ (world?.road_anchors ?? []).length }}</span>
            </li>
            <li class="flex justify-between gap-3">
              <span>Highways / country</span><span>{{ highwayCount }} / {{ countryCount }}</span>
            </li>
            <li class="flex justify-between gap-3">
              <span>Town streets</span><span>{{ townCount }}</span>
            </li>
            <li class="flex justify-between gap-3">
              <span>Access lanes</span><span>{{ accessCount }}</span>
            </li>
          </ul>
        </section>

        <section class="rounded-lg border border-theme-primary/25 bg-surface p-4">
          <h2 class="mb-3 text-xs font-bold uppercase tracking-[0.2em] text-theme-primary">
            Regions
          </h2>
          <ul class="space-y-3 text-xs text-theme-primary/80">
            <li v-for="region in regionStats" :key="region.id" class="space-y-1">
              <div class="flex items-center justify-between gap-3">
                <span class="flex items-center gap-2">
                  <span class="size-3 rounded-sm border border-theme-primary/40" :class="region.colorClass" />
                  <span class="font-bold text-theme-primary">{{ region.name }}</span>
                </span>
                <span class="text-theme-primary/50">tier {{ region.danger_tier }}</span>
              </div>
              <p class="text-theme-primary/55">
                {{ region.tiles }} tiles · {{ region.in_main_component }} reachable · water
                {{ region.terrain.water ?? 0 }} · forest {{ region.terrain.forest ?? 0 }}
              </p>
            </li>
          </ul>
        </section>

        <section class="rounded-lg border border-theme-primary/25 bg-surface p-4">
          <h2 class="mb-3 text-xs font-bold uppercase tracking-[0.2em] text-theme-primary">
            Validation
          </h2>
          <ul class="space-y-1 text-xs text-theme-primary/80">
            <li class="flex justify-between gap-3">
              <span>Reachable vault slots</span>
              <span>{{ validation.reachableSlots }} / {{ validation.slotTiles }}</span>
            </li>
            <li class="flex justify-between gap-3">
              <span>Slots with road access</span>
              <span>{{ validation.slotsWithRoad }} / {{ world?.slots.length ?? 0 }}</span>
            </li>
            <li class="flex justify-between gap-3">
              <span>Max slot road distance</span>
              <span>{{ validation.maxSlotDistance }} tiles</span>
            </li>
            <li class="flex justify-between gap-3">
              <span>Land within 5 tiles</span>
              <span>{{ Math.round(validation.coverage * 100) }}%</span>
            </li>
            <li class="flex justify-between gap-3">
              <span>Highway components</span>
              <span>{{ validation.highwayComponents }}</span>
            </li>
            <li class="flex justify-between gap-3">
              <span>Min hub degree</span>
              <span>{{ validation.minHubDegree }}</span>
            </li>
            <li class="flex justify-between gap-3">
              <span>Isolated regions</span>
              <span>{{ validation.isolated.length }}</span>
            </li>
          </ul>
          <p v-if="validation.isolated.length" class="mt-2 text-xs text-status-fighting">
            {{ validation.isolated.join(', ') }}
          </p>
        </section>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.lab-grid line {
  stroke: var(--color-theme-primary);
  stroke-width: 0.05;
  opacity: 0.14;
}
.lab-slots circle {
  fill: none;
  stroke: var(--color-theme-primary);
  stroke-width: 0.25;
  opacity: 0.55;
}
.lab-anchors rect {
  fill: none;
  stroke: var(--color-atlas-amber);
  stroke-width: 0.3;
  opacity: 0.6;
}
.lab-places circle {
  fill: var(--color-theme-primary);
  fill-opacity: 0.28;
  stroke: var(--color-theme-primary);
  stroke-width: 0.35;
}
.lab-origin circle {
  fill: none;
  stroke: var(--color-atlas-amber);
  stroke-width: 0.5;
}
.lab-region-labels text {
  fill: var(--color-theme-primary);
  font-size: 4.6px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  opacity: 0.72;
}
</style>
