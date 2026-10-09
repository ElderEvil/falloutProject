<script setup lang="ts">
/**
 * THROWAWAY DEV ARTIFACT — `/dev/map-mockup` decision mockup.
 *
 * Renders the REAL map components (WorldMap + MapMarker) with curated fixtures
 * so the next map-improvement release can be judged visually before any
 * production code changes. Delete this view (or promote the winning ideas into
 * production, then delete) once the visual direction is decided.
 *
 * Dev-only: reachable exclusively through the `import.meta.env.DEV` router
 * block, never linked from navigation, no backend/auth calls, deterministic.
 */
import { computed, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { Badge } from '@/core/components/ui/badge'
import { Button } from '@/core/components/ui/button'
import { Progress } from '@/core/components/ui/progress'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/core/components/ui/select'
import { Switch } from '@/core/components/ui/switch'
import { ToggleGroup, ToggleGroupItem } from '@/core/components/ui/toggle-group'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import DwellerStatusBadge from '@/modules/dwellers/components/stats/DwellerStatusBadge.vue'
import MapMarker from '../components/MapMarker.vue'
import WorldMap from '../components/WorldMap.vue'
import { useMapStore } from '../stores/map'
import { groupColor } from '../models/groupColors'
import type { MarkerClickPayload } from '../models/map'
import {
  MOCK_DISCOVERY_ROUTES,
  MOCK_DWELLER_PREVIEW,
  MOCK_EXPEDITION_SITES,
  MOCK_EXPLORER_TRACKS,
  MOCK_HOME_VAULT_ID,
  MOCK_LOCATIONS,
  MOCK_PLAYER_VAULTS,
  MOCK_UNSEEN_DISCOVERY_ID,
  MOCK_VAULT_MARKERS,
  PLACE_GROUPS,
  buildMockWorldSnapshot,
} from '../dev/mapMockupData'

const mapStore = useMapStore()

// Group-icon candidates for the icon-set review. The first entry of each group
// is the recommendation; the rest are alternatives. Preview only — the backend
// catalog is unchanged until one is signed off per group.
const ICON_CANDIDATE_GROUPS = [
  {
    label: 'Military — candidates',
    candidates: [
      { icon: 'mdi:tank', label: 'Tank (recommended)' },
      { icon: 'mdi:ammunition', label: 'Ammunition' },
      { icon: 'mdi:radar', label: 'Radar' },
      { icon: 'mdi:target', label: 'Target' },
    ],
  },
  {
    label: 'Brotherhood Outpost — candidates',
    candidates: [
      { icon: 'mdi:shield-star', label: 'Shield Star (recommended)' },
      { icon: 'mdi:hammer-wrench', label: 'Hammer & Wrench' },
      { icon: 'mdi:cog', label: 'Cog' },
      { icon: 'mdi:robot', label: 'Robot' },
    ],
  },
] as const

// Seed the real store before WorldMap mounts: place groups drive per-group
// marker icon resolution, the snapshot drives the real AtlasTerrain render.
mapStore.placeGroups = PLACE_GROUPS
mapStore.worldSnapshot = buildMockWorldSnapshot()

// All discoveries read as "viewed" except one, so the unseen pulse is visible.
for (const location of MOCK_LOCATIONS) {
  if (location.type !== 'discovery' || location.id === MOCK_UNSEEN_DISCOVERY_ID) continue
  mapStore.markLocationViewed(MOCK_HOME_VAULT_ID, location.id)
}

type VisibilityFilter = 'all' | 'discovered' | 'locked'

const selectedGroupKey = ref('all')
const visibilityFilter = ref<VisibilityFilter>('all')
// Default off so every fixture is visible without exploring the fog first.
const fogDisabled = ref(true)
// Group-colour experiment: tint known markers by place group instead of state.
const groupColors = ref(false)
const selectedMarkerId = ref<string | null>(null)
const dwellerPopoverOpen = ref(false)

const filteredLocations = computed(() =>
  MOCK_LOCATIONS.filter((location) => {
    if (selectedGroupKey.value !== 'all' && location.group_key !== selectedGroupKey.value) {
      return false
    }
    if (visibilityFilter.value === 'discovered' && !location.is_unlocked) return false
    if (visibilityFilter.value === 'locked' && location.is_unlocked) return false
    return true
  })
)

function onGroupSelect(value: unknown): void {
  if (typeof value === 'string') selectedGroupKey.value = value
}

function onVisibilitySelect(value: unknown): void {
  if (value === 'all' || value === 'discovered' || value === 'locked') {
    visibilityFilter.value = value
  }
}

function onMarkerClick(payload: MarkerClickPayload): void {
  if (payload.kind === 'location') {
    selectedMarkerId.value = `loc-${payload.data.id}`
  } else if (payload.kind === 'site') {
    selectedMarkerId.value = `site-${payload.data.id}`
  } else {
    selectedMarkerId.value = `vault-${payload.data.name}`
  }
}
</script>

<template>
  <div class="mx-auto max-w-6xl px-4 py-8 font-mono text-theme-primary sm:px-6">
    <!-- Dev-only banner: what this page is and is not -->
    <div class="flex flex-wrap items-center gap-3 border border-warning/60 bg-warning/10 px-4 py-3">
      <Badge variant="outline" class="border-warning/60 text-warning">DEV ONLY</Badge>
      <p class="text-sm">
        Throwaway decision mockup with fixture data — no backend, no auth. The map below is the
        real <code>WorldMap</code>; this page is compiled out of production and never linked in
        navigation. Delete it once the map direction is decided.
      </p>
    </div>

    <header class="mt-6">
      <h1 class="text-3xl font-bold terminal-glow">Map Mockup</h1>
      <p class="mt-2 max-w-3xl text-sm text-theme-primary/60">
        Judge the proposed map controls and clickable-dweller interaction against the real
        component behavior before implementing.
      </p>
    </header>

    <!-- ============ Proposed controls ============ -->
    <section class="mt-8" aria-labelledby="h-controls">
      <h2 id="h-controls" class="mb-4 border-b-2 border-theme-primary/30 pb-2 text-xl font-bold">
        Proposed controls
      </h2>
      <div class="flex flex-wrap items-end gap-6 border border-theme-primary/30 bg-surface p-4">
        <div class="flex flex-col gap-1.5">
          <span class="text-xs tracking-wider uppercase text-theme-primary/60">Group / site type</span>
          <Select :model-value="selectedGroupKey" @update:model-value="onGroupSelect">
            <SelectTrigger class="w-56" aria-label="Filter locations by place group">
              <SelectValue placeholder="All groups" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All groups</SelectItem>
              <SelectItem v-for="group in PLACE_GROUPS" :key="group.key" :value="group.key">
                {{ group.label }}
              </SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div class="flex flex-col gap-1.5">
          <span class="text-xs tracking-wider uppercase text-theme-primary/60">Discovered state</span>
          <ToggleGroup
            type="single"
            variant="outline"
            :model-value="visibilityFilter"
            :spacing="0"
            @update:model-value="onVisibilitySelect"
          >
            <!-- @vue-ignore -->
            <ToggleGroupItem value="all">All</ToggleGroupItem>
            <!-- @vue-ignore -->
            <ToggleGroupItem value="discovered">Discovered</ToggleGroupItem>
            <!-- @vue-ignore -->
            <ToggleGroupItem value="locked">Locked</ToggleGroupItem>
          </ToggleGroup>
        </div>

        <div class="flex items-center gap-2 pb-1.5">
          <Switch id="mockup-fog" v-model:checked="fogDisabled" aria-label="Disable fog of war" />
          <label
            for="mockup-fog"
            class="cursor-pointer text-xs tracking-wider uppercase text-theme-primary/60"
          >
            Fog disabled (all fixtures visible)
          </label>
        </div>

        <div class="flex items-center gap-2 pb-1.5">
          <Switch
            id="mockup-group-colors"
            v-model:checked="groupColors"
            aria-label="Color markers by place group"
          />
          <label
            for="mockup-group-colors"
            class="cursor-pointer text-xs tracking-wider uppercase text-theme-primary/60"
          >
            Group colors (experiment)
          </label>
        </div>

        <div class="ml-auto text-right">
          <p class="text-2xl font-bold terminal-glow">{{ filteredLocations.length }}</p>
          <p class="text-xs tracking-wider uppercase text-theme-primary/60">locations shown</p>
        </div>
      </div>
    </section>

    <!-- ============ Real WorldMap ============ -->
    <section class="mt-10" aria-labelledby="h-worldmap">
      <h2 id="h-worldmap" class="mb-2 border-b-2 border-theme-primary/30 pb-2 text-xl font-bold">
        Real WorldMap — curated fixtures
      </h2>
      <p class="mb-2 max-w-3xl text-sm text-theme-primary/60">
        Identical production component: zoom/pan, cluster badges, declutter thresholds, locked
        hint pins, route casing and the docked index all behave exactly as shipped. Origins,
        visited places and anonymous vault signals reappear once you zoom past 150%.
      </p>
      <p class="mb-4 max-w-3xl text-xs tracking-wide text-theme-primary/55">
        Marker color = state: green known · grey unknown/locked · dimmed cleared · amber vault
        signal · accent explorer · pulsing unseen discovery. The glyph identifies the site type.
        Toggle "Group colors" to tint known markers by site type instead (state still wins for
        locked / cleared / vault / explorer).
      </p>
      <WorldMap
        :locations="filteredLocations"
        :vault-markers="MOCK_VAULT_MARKERS"
        :player-vaults="MOCK_PLAYER_VAULTS"
        :discovery-routes="MOCK_DISCOVERY_ROUTES"
        :expedition-sites="MOCK_EXPEDITION_SITES"
        :explorer-tracks="MOCK_EXPLORER_TRACKS"
        :fog-disabled="fogDisabled"
        :group-colors="groupColors"
        :selected-marker-id="selectedMarkerId"
        @update:selected-marker-id="selectedMarkerId = $event"
        @marker-click="onMarkerClick"
      />
    </section>

    <!-- ============ Proposed clickable dweller ============ -->
    <section class="mt-10" aria-labelledby="h-dweller-preview">
      <h2
        id="h-dweller-preview"
        class="mb-2 border-b-2 border-theme-primary/30 pb-2 text-xl font-bold"
      >
        <span class="text-warning">PROPOSED</span> — clickable dweller
      </h2>
      <p class="mb-4 max-w-3xl text-sm text-theme-primary/60">
        Production renders free-roam explorer last-known markers with
        <code>interactive: false</code>. Proposal: clicking one opens this popover — portrait,
        status, HP/radiation, current task and a details action.
      </p>
      <div class="relative w-fit border border-theme-primary bg-terminal-background p-2 crt-screen">
        <svg
          viewBox="0 0 160 160"
          class="block h-72 w-72"
          aria-label="Clickable explorer marker preview"
        >
          <MapMarker
            :x="80"
            :y="80"
            name="Sarah Lyons"
            type="explorer"
            icon="mdi:account"
            label="Explorer"
            status="Last known — Sarah Lyons"
            :interactive="true"
            :selected="dwellerPopoverOpen"
            @click="dwellerPopoverOpen = !dwellerPopoverOpen"
          />
        </svg>
        <p
          v-if="!dwellerPopoverOpen"
          class="pointer-events-none absolute bottom-3 left-1/2 -translate-x-1/2 text-xs tracking-wider uppercase text-theme-primary/50"
        >
          Click the marker
        </p>

        <!-- Proposed dweller popover (static preview, anchored beside the marker) -->
        <div
          v-if="dwellerPopoverOpen"
          role="dialog"
          aria-label="Proposed dweller popover"
          class="absolute top-1/2 left-1/2 z-10 ml-10 w-64 -translate-y-1/2 border border-theme-primary bg-surface p-3 shadow-glow-md"
        >
          <div class="flex items-start gap-3">
            <DwellerPortrait
              alt="Sarah Lyons"
              fallback-icon="mdi:account"
              image-class="h-12 w-12 shrink-0 rounded-full border border-theme-primary object-cover object-top"
              fallback-class="block h-12 w-12 shrink-0"
            />
            <div class="min-w-0">
              <p class="truncate text-sm font-bold">{{ MOCK_DWELLER_PREVIEW.name }}</p>
              <DwellerStatusBadge
                :status="MOCK_DWELLER_PREVIEW.status"
                :show-label="true"
                size="small"
                class="mt-1"
              />
            </div>
          </div>

          <div class="mt-3 space-y-3">
            <div>
              <div
                class="flex items-baseline justify-between text-[10px] tracking-wider uppercase text-theme-primary/60"
              >
                <span>HP</span>
                <span>{{ MOCK_DWELLER_PREVIEW.hitPoints }} / 100</span>
              </div>
              <!-- @vue-ignore -->
              <Progress
                :model-value="MOCK_DWELLER_PREVIEW.hitPoints"
                size="xs"
                tone="success"
                label="Hit points"
                class="mt-1"
              />
            </div>
            <div>
              <div
                class="flex items-baseline justify-between text-[10px] tracking-wider uppercase text-theme-primary/60"
              >
                <span>Radiation</span>
                <span>{{ MOCK_DWELLER_PREVIEW.radiation }} / 100</span>
              </div>
              <!-- @vue-ignore -->
              <Progress
                :model-value="MOCK_DWELLER_PREVIEW.radiation"
                size="xs"
                tone="warning"
                label="Radiation"
                class="mt-1"
              />
            </div>
          </div>

          <p class="mt-3 text-xs text-theme-primary/70">
            Current task:
            <span class="text-theme-primary">{{ MOCK_DWELLER_PREVIEW.task }}</span>
          </p>

          <Button size="sm" class="mt-3 w-full">View details</Button>
        </div>
      </div>
    </section>

    <!-- ============ Group icon reference ============ -->
    <section class="mt-10 pb-16" aria-labelledby="h-icon-reference">
      <h2
        id="h-icon-reference"
        class="mb-2 border-b-2 border-theme-primary/30 pb-2 text-xl font-bold"
      >
        Group icon reference — 17 groups + locked state
      </h2>
      <p class="mb-4 max-w-3xl text-sm text-theme-primary/60">
        Every catalog icon at marker size, next to the dimmed locked "Unknown Location" state.
        Use this to judge icon distinctness (the generic-compass fallback problem) before choosing
        the next icon set.
      </p>
      <div class="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
        <div
          v-for="group in PLACE_GROUPS"
          :key="group.key"
          class="flex items-center gap-2 border border-theme-primary/25 bg-surface px-2.5 py-2"
        >
          <Icon
            :icon="group.icon"
            class="h-5 w-5 shrink-0"
            :style="groupColors ? { color: groupColor(group.key) } : undefined"
          />
          <span class="min-w-0 truncate text-xs">{{ group.label }}</span>
        </div>
        <div
          class="flex items-center gap-2 border border-dashed border-theme-primary/25 bg-surface px-2.5 py-2"
        >
          <Icon icon="mdi:lock-question" class="h-5 w-5 shrink-0 opacity-50" />
          <span class="min-w-0 truncate text-xs opacity-70">Unknown Location</span>
        </div>
      </div>

      <!-- Group-icon candidates — preview only, backend catalog untouched -->
      <div class="mt-4 space-y-3">
        <div
          v-for="group in ICON_CANDIDATE_GROUPS"
          :key="group.label"
          class="border border-dashed border-warning/50 bg-surface px-3 py-2"
        >
          <div class="mb-2 flex flex-wrap items-center gap-2">
            <Badge variant="outline" class="border-warning/60 text-warning">CANDIDATE PREVIEW</Badge>
            <span class="text-xs tracking-wider uppercase text-theme-primary/60">
              {{ group.label }}
            </span>
          </div>
          <div class="flex flex-wrap gap-x-5 gap-y-2">
            <div
              v-for="candidate in group.candidates"
              :key="candidate.icon"
              class="flex items-center gap-2"
            >
              <Icon :icon="candidate.icon" class="h-5 w-5 shrink-0" />
              <span class="text-xs">
                {{ candidate.label }}
                <code class="text-theme-primary/50">{{ candidate.icon }}</code>
              </span>
            </div>
          </div>
        </div>
        <p class="px-0.5 text-xs text-theme-primary/50">
          Preview only — the backend place-group catalog keeps its current icon until one is
          chosen.
        </p>
      </div>
    </section>
  </div>
</template>
