<script setup lang="ts">
import { computed, ref, useId } from 'vue'
import { useElementSize } from '@vueuse/core'
import { RouterLink } from 'vue-router'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import { Switch } from '@/core/components/ui/switch'
import WorldMap from '../components/WorldMap.vue'
import {
  ATLAS_TERRAIN_CLASS,
  ATLAS_TERRAIN_LABEL,
  ATLAS_TERRAIN_ORDER,
} from '../utils/atlasProjection'
import { isKnownLocation } from '../utils/visibility'
import type { MarkerClickPayload } from '../models/map'
import {
  denseLocations,
  previewGroups,
  previewLocations,
  previewRoutes,
  previewSites,
  previewSnapshot,
  terrainRelief,
} from '../dev/mapPreview'

const designs = [
  {
    id: 'atlas',
    number: '01',
    name: 'Regional atlas',
    subtitle: 'A map worth unfolding',
    icon: 'mdi:map-outline',
    description:
      'Amber instrument frame and illustrated terrain marks, with places and legend on the right. Closest to the reference.',
  },
  {
    id: 'field',
    number: '02',
    name: 'Field chart',
    subtitle: 'Made for the journey',
    icon: 'mdi:compass-outline',
    description:
      'A wide survey chart with a compact header and a separate registry. More room for the terrain.',
  },
  {
    id: 'terminal',
    number: '03',
    name: 'Survey terminal',
    subtitle: 'The familiar signal',
    icon: 'mdi:monitor',
    description: 'The current CRT palette and quiet terrain, with the same working map controls.',
  },
] as const
const design = ref<(typeof designs)[number]['id']>('atlas')
const selectedDesign = computed(() => designs.find((item) => item.id === design.value)!)
const fog = ref(false)
const dense = ref(false)
const illustrated = ref(true)
const plateLoaded = ref(false)
const plateFailed = ref(false)
const plateUrl = '/__dev/map-plate.png'
const chromeUrl = '/__dev/map-chrome.svg'
const chromeFailed = ref(false)
const scaleElement = ref<SVGSVGElement | null>(null)
const { width: scalePixels } = useElementSize(scaleElement)
const showIllustration = computed(
  () => illustrated.value && plateLoaded.value && !plateFailed.value
)
const selectedMarkerId = ref<string | null>(null)
const selectedPlace = ref({
  name: 'Your next discovery awaits',
  detail: 'Select a marker to inspect the chart.',
})
const locations = computed(() =>
  dense.value ? [...previewLocations, ...denseLocations] : previewLocations
)
const textureId = useId()
const gridId = useId()

function scaleDistance(zoom: number, mapPixelWidth: number): string {
  if (mapPixelWidth <= 0) return '—'
  // The square map spans 100 registry units at 100% zoom.
  const units = (100 / zoom) * (scalePixels.value / mapPixelWidth)
  return new Intl.NumberFormat('en', { maximumFractionDigits: 1 }).format(units)
}

function selectMarker(payload: MarkerClickPayload): void {
  if (payload.kind === 'location') {
    selectedPlace.value = isKnownLocation(payload.data)
      ? {
          name: payload.data.name,
          detail: payload.data.description ?? 'Recorded in the regional survey.',
        }
      : { name: 'Unidentified signal', detail: 'Explore this region to identify the location.' }
  } else if (payload.kind === 'site') {
    selectedPlace.value = { name: payload.data.name, detail: payload.data.flavor }
  }
}
</script>

<template>
  <main class="map-designs mx-auto max-w-[1480px] space-y-7 px-4 py-6 font-mono sm:px-8 sm:py-9">
    <header class="space-y-4">
      <RouterLink
        to="/dev"
        class="inline-flex items-center gap-2 text-xs text-atlas-paper/70 underline-offset-4 hover:underline"
      >
        <Icon icon="mdi:arrow-left" class="size-4" /> Development tools
      </RouterLink>
      <div class="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p class="mb-2 text-[10px] uppercase tracking-[.3em] text-atlas-amber">
            Vault-Tec cartography division
          </p>
          <h1 class="text-2xl font-bold uppercase tracking-tight text-atlas-paper sm:text-4xl">
            A better view of the wasteland.
          </h1>
        </div>
        <p class="max-w-sm text-xs leading-relaxed text-atlas-paper/60">
          Experimental draft. Compare three designs using preview data and working map controls.
        </p>
      </div>
    </header>

    <nav aria-label="Map design" class="grid gap-2 sm:grid-cols-3">
      <Button
        v-for="item in designs"
        :key="item.id"
        variant="ghost"
        :aria-pressed="design === item.id"
        class="design-choice h-auto justify-start gap-4 whitespace-normal rounded-none border p-4 text-left"
        :class="
          design === item.id
            ? 'border-atlas-amber bg-atlas-amber/10 text-atlas-amber'
            : 'border-atlas-paper/15 text-atlas-paper/60'
        "
        @click="design = item.id"
      >
        <span class="text-xs opacity-50">{{ item.number }}</span>
        <span class="flex-1"
          ><span class="block text-sm font-bold uppercase tracking-wider">{{ item.name }}</span
          ><span class="mt-1 block text-xs font-normal opacity-70">{{ item.subtitle }}</span></span
        >
        <Icon :icon="item.icon" class="size-6 shrink-0" />
      </Button>
    </nav>

    <div class="flex flex-wrap items-center justify-between gap-4 text-xs text-atlas-paper/75">
      <p class="max-w-2xl leading-relaxed">{{ selectedDesign.description }}</p>
      <div class="flex flex-wrap gap-5">
        <label class="flex items-center gap-2"
          ><Switch v-model:checked="illustrated" aria-label="Illustrated terrain" /> Illustrated
          terrain</label
        >
        <label class="flex items-center gap-2"
          ><Switch v-model:checked="fog" aria-label="Fog of war" /> Fog of war</label
        >
        <label class="flex items-center gap-2"
          ><Switch v-model:checked="dense" aria-label="Dense markers" /> Dense markers</label
        >
      </div>
    </div>

    <p v-if="illustrated && plateFailed" class="text-xs text-atlas-paper/70" role="status">
      Local illustration unavailable. Showing procedural terrain.
    </p>

    <section
      class="design-sheet"
      :class="`design-sheet--${design}`"
      :aria-label="`${selectedDesign.name} preview`"
    >
      <header v-if="design !== 'terminal'" class="chart-masthead">
        <div class="flex min-w-0 items-center gap-3 sm:gap-5">
          <svg
            v-if="!chromeFailed"
            viewBox="16 12 320 72"
            class="h-14 w-60 sm:h-16 sm:w-72"
            role="img"
            aria-label="Vault-Tec regional map"
          >
            <image :href="chromeUrl" width="1024" height="1024" @error="chromeFailed = true" />
          </svg>
          <template v-else>
            <svg
              class="chart-emblem size-11 shrink-0 sm:size-14"
              viewBox="0 0 84 52"
              fill="currentColor"
              aria-hidden="true"
            >
              <path
                d="M4 13h20l-5 6H1l-1-2Zm-3 12h17v6H0Zm3 18h20l-5-6H1l-1 2ZM80 13H60l5 6h18l1-2Zm3 12H66v6h18Zm-3 18H60l5-6h18l1 2Z"
              />
              <circle cx="42" cy="27" r="23" fill="none" stroke="currentColor" stroke-width="5" />
              <circle cx="42" cy="27" r="11" />
            </svg>
            <div class="min-w-0">
              <p class="chart-eyebrow">Vault-Tec</p>
              <h2 class="chart-title">
                {{ design === 'atlas' ? 'Regional map' : 'Wasteland field chart' }}
              </h2>
            </div>
          </template>
        </div>
        <div class="chart-edition"><span>REGIONAL SURVEY</span><span>FIELD EDITION / 01</span></div>
      </header>

      <WorldMap
        :key="design"
        v-model:selected-marker-id="selectedMarkerId"
        class="study-map"
        :locations="locations"
        :vault-markers="[]"
        :discovery-routes="previewRoutes"
        :expedition-sites="previewSites"
        :snapshot="previewSnapshot"
        :terrain-palette="design === 'terminal' ? undefined : 'atlas'"
        :place-groups="previewGroups"
        :fog-disabled="!fog"
        overview
        @marker-click="selectMarker"
      >
        <template #terrain-overlay>
          <defs>
            <pattern :id="gridId" width="8" height="8" patternUnits="userSpaceOnUse"
              ><path d="M8 0H0V8" fill="none" class="chart-grid" stroke-width=".12"
            /></pattern>
            <pattern :id="`${gridId}-minor`" width="2" height="2" patternUnits="userSpaceOnUse">
              <path
                d="M2 0H0V2"
                fill="none"
                class="chart-grid chart-grid-minor"
                stroke-width=".06"
              />
            </pattern>
            <filter :id="textureId"
              ><feTurbulence
                type="fractalNoise"
                baseFrequency=".85"
                numOctaves="3"
                stitchTiles="stitch" /><feColorMatrix type="saturate" values="0"
            /></filter>
          </defs>
          <g
            v-if="design !== 'terminal' && !showIllustration"
            class="terrain-relief"
            aria-hidden="true"
            pointer-events="none"
          >
            <path :d="terrainRelief.forest" class="relief-forest" />
            <path :d="terrainRelief.hills" class="relief-hills" />
            <path :d="terrainRelief.ruins" class="relief-ruins" />
            <path :d="terrainRelief.water" class="relief-water" />
            <path :d="terrainRelief.wasteland" class="relief-wasteland" />
            <rect width="160" height="160" :filter="`url(#${textureId})`" class="chart-grain" />
          </g>
          <image
            v-if="illustrated && !plateFailed"
            class="illustrated-plate"
            :href="plateUrl"
            x="0"
            y="0"
            width="160"
            height="160"
            preserveAspectRatio="none"
            :opacity="plateLoaded ? 1 : 0"
            pointer-events="none"
            aria-hidden="true"
            @load="plateLoaded = true"
            @error="plateFailed = true"
          />
          <g class="map-grid" aria-hidden="true" pointer-events="none">
            <rect width="160" height="160" :fill="`url(#${gridId}-minor)`" />
            <rect width="160" height="160" :fill="`url(#${gridId})`" />
          </g>
        </template>
        <template #legend-intro>
          <section class="biome-key" aria-label="Biome legend">
            <h2 class="border-b border-current/60 pb-2 text-lg font-bold uppercase tracking-[.2em]">
              Biomes
            </h2>
            <ul class="mt-3 grid gap-2">
              <li
                v-for="terrain in ATLAS_TERRAIN_ORDER"
                :key="terrain"
                class="flex items-center gap-3 text-sm font-semibold tracking-wide"
              >
                <span
                  aria-hidden="true"
                  class="biome-swatch h-7 w-10 shrink-0 rounded border border-current"
                  :class="ATLAS_TERRAIN_CLASS[terrain]"
                />{{ ATLAS_TERRAIN_LABEL[terrain] }}
              </li>
            </ul>
          </section>
        </template>
        <template v-if="design !== 'terminal'" #map-chrome="{ zoom, mapPixelWidth }">
          <div
            class="chart-compass pointer-events-none absolute bottom-4 left-4 z-10 flex items-end gap-3 sm:gap-4"
          >
            <svg
              v-if="!chromeFailed"
              viewBox="17 810 152 149"
              class="reference-compass size-16 sm:size-24"
              role="img"
              aria-label="Compass, north is up"
            >
              <image :href="chromeUrl" width="1024" height="1024" @error="chromeFailed = true" />
            </svg>
            <svg
              v-else
              viewBox="0 0 72 72"
              class="size-16 sm:size-24"
              role="img"
              aria-label="Compass, north is up"
            >
              <circle cx="36" cy="36" r="28" fill="none" stroke="currentColor" stroke-width="1" />
              <circle cx="36" cy="36" r="23" fill="none" stroke="currentColor" stroke-width=".5" />
              <path d="m36 3 6 27 27 6-27 6-6 27-6-27-27-6 27-6Z" fill="currentColor" />
              <circle
                cx="36"
                cy="36"
                r="8"
                class="compass-centre"
                stroke="currentColor"
                stroke-width="2"
              />
            </svg>
            <div
              class="mb-1 flex flex-col gap-1 text-[8px] tracking-wider sm:text-[9px]"
              aria-label="Map distance scale"
            >
              <div class="flex justify-between">
                <span>0</span
                ><span class="scale-distance">{{ scaleDistance(zoom, mapPixelWidth) }}</span>
              </div>
              <svg
                ref="scaleElement"
                :viewBox="chromeFailed ? '0 0 205 18' : '158 958 205 18'"
                class="reference-scale h-4 w-28 sm:w-44"
                aria-hidden="true"
              >
                <image
                  v-if="!chromeFailed"
                  :href="chromeUrl"
                  width="1024"
                  height="1024"
                  @error="chromeFailed = true"
                />
                <path
                  v-else
                  d="M1 1V12H204V1M42 12V6M83 12V6M124 12V6M165 12V6"
                  fill="none"
                  stroke="currentColor"
                />
              </svg>
              <span class="text-center">MAP UNITS</span>
            </div>
          </div>
          <div
            class="chart-stamp pointer-events-none absolute bottom-4 right-4 z-10 hidden items-center gap-3 border px-3 py-2 sm:flex"
          >
            <Icon icon="mdi:radioactive" class="size-6" /><span
              class="text-[10px] uppercase tracking-[.2em]"
              >Wasteland survey<br /><span class="text-[8px] opacity-60"
                >Explore. Record. Survive.</span
              ></span
            >
          </div>
        </template>
      </WorldMap>

      <footer
        class="chart-footer flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-[10px] uppercase tracking-wider sm:px-6"
      >
        <span class="flex items-center gap-2"
          ><span class="size-1.5 rounded-full bg-current" /> SCOUT TRAILS · NORTH UP</span
        >
        <span>{{ locations.length }} PLACES / {{ previewSites.length }} SITE</span>
      </footer>
    </section>

    <section
      class="flex flex-wrap items-start justify-between gap-5 border-t border-atlas-paper/20 pt-5"
      aria-label="Selected place"
    >
      <div class="flex gap-3">
        <Icon icon="mdi:map-marker-outline" class="mt-1 size-6 text-atlas-amber" />
        <div>
          <p class="mb-1 text-[9px] uppercase tracking-[.2em] text-atlas-paper/50">Field notes</p>
          <h3 class="font-bold text-atlas-paper">{{ selectedPlace.name }}</h3>
          <p class="mt-1 text-xs text-atlas-paper/65">{{ selectedPlace.detail }}</p>
        </div>
      </div>
      <p class="max-w-xs text-[10px] leading-relaxed text-atlas-paper/45">
        Preview data only. Markers, fog, and controls are interactive; no vault or expedition is
        changed.
      </p>
    </section>
  </main>
</template>

<style scoped>
@reference '../../../assets/tailwind.css';

.map-designs {
  background: var(--color-surface-canvas);
  --color-theme-primary: var(--color-atlas-amber);
  --primary: var(--color-atlas-amber);
  --foreground: var(--color-atlas-amber);
  --ring: var(--color-atlas-amber);
  text-shadow: none;
}
.map-designs :is(h1, h2, h3) {
  text-shadow: none;
}
.design-choice:hover {
  background: color-mix(in srgb, var(--color-atlas-amber) 8%, transparent);
}
.design-sheet {
  --color-theme-primary: var(--color-atlas-amber);
  --color-theme-accent: var(--color-atlas-amber);
  --color-theme-glow: color-mix(in srgb, var(--color-atlas-amber) 25%, transparent);
  --color-terminal-background: var(--color-atlas-ink);
  --primary: var(--color-atlas-amber);
  --foreground: var(--color-atlas-amber);
  color: var(--color-atlas-amber);
  background: var(--color-atlas-ink);
  border: 2px solid currentColor;
}
.design-sheet--atlas {
  border-radius: 20px;
  padding: 6px;
  max-width: 1100px;
  margin-inline: auto;
}
.chart-masthead {
  @apply flex items-center justify-between gap-3 border-b border-current/35 px-4 py-4 sm:px-6;
}
.chart-eyebrow {
  @apply text-[10px] font-bold uppercase tracking-[.3em];
}
.chart-title {
  @apply mt-1 text-lg font-bold uppercase tracking-[.12em] sm:text-2xl;
}
.chart-edition {
  @apply hidden text-right text-[9px] leading-loose tracking-[.15em] sm:grid;
}
.biome-key {
  @apply m-3 rounded-xl border-2 border-current px-3 py-3;
  background: var(--color-atlas-ink);
}
.chart-stamp {
  @apply rounded-xl;
  background: var(--color-atlas-ink);
}
.compass-centre {
  fill: var(--color-atlas-ink);
}
.chart-footer {
  border-top: 1px solid color-mix(in srgb, currentColor 35%, transparent);
}
.design-sheet--atlas :deep(.world-map-layout) {
  @apply gap-3 p-3;
}
.design-sheet--atlas :deep(.world-map-container) {
  @apply rounded-xl border border-current/60;
  box-shadow: none;
}
.design-sheet--atlas :deep(.map-index .marker-list-panel) {
  @apply overflow-hidden rounded-xl;
}
.design-sheet--atlas :deep(.world-map-container.crt-screen::before),
.design-sheet--field :deep(.world-map-container.crt-screen::before) {
  display: none;
}
.design-sheet--field {
  @apply rounded-none;
  color: var(--color-atlas-paper);
}
.design-sheet--field .chart-masthead {
  @apply py-3;
}
.design-sheet--field .chart-title {
  @apply text-base sm:text-lg;
}
.design-sheet--field .chart-emblem {
  @apply size-9;
}
.design-sheet--field :deep(.world-map-layout) {
  @apply gap-0;
}
.design-sheet--field :deep(.world-map-container) {
  --map-pane-size: clamp(400px, 65vh, 720px);
  border: 0;
}
.design-sheet--field :deep(.map-index) {
  @apply border-l border-current/25;
}
.design-sheet--field .chart-compass {
  @apply bottom-3 left-3;
}
.design-sheet--terminal {
  --color-theme-primary: var(--theme-primary, var(--color-happiness-high));
  --color-theme-accent: var(--theme-accent, var(--color-atlas-amber));
  --primary: var(--color-theme-primary);
  --foreground: var(--color-theme-primary);
  @apply border-theme-primary/40;
  color: var(--color-theme-primary);
}
.design-sheet--terminal :deep(.world-map-container) {
  --map-pane-size: clamp(400px, 65vh, 720px);
}
.study-map :deep(.world-map-container) {
  height: auto;
  aspect-ratio: 1;
}
@media (min-width: 1280px) {
  .study-map :deep(.map-index) {
    align-self: stretch;
  }
  .study-map :deep(.map-index .marker-list-panel) {
    height: 100%;
    max-height: none;
    margin-top: 0;
  }
}
.study-map :deep(.zoom-controls) {
  @apply left-4 top-4;
}
.study-map :deep(.zoom-btn) {
  @apply size-9 rounded-md;
}
.study-map :deep(.marker-backing) {
  fill: var(--color-atlas-ink);
  filter: none;
}
.chart-grid {
  stroke: var(--color-atlas-amber);
  opacity: 0.35;
}
.chart-grid-minor {
  opacity: 0.08;
}
.chart-grain {
  opacity: 0.11;
  mix-blend-mode: soft-light;
}
.relief-forest {
  fill: var(--color-atlas-ink);
  opacity: 0.6;
}
.relief-hills {
  fill: none;
  stroke: var(--color-atlas-paper);
  stroke-width: 0.2;
  opacity: 0.5;
}
.relief-ruins {
  fill: none;
  stroke: var(--color-atlas-ink);
  stroke-width: 0.4;
  opacity: 0.6;
}
.relief-water {
  fill: none;
  stroke: var(--color-atlas-paper);
  stroke-width: 0.15;
  opacity: 0.25;
}
.relief-wasteland {
  stroke: var(--color-atlas-ink);
  stroke-width: 0.5;
  opacity: 0.3;
}
.design-sheet:not(.design-sheet--terminal) .biome-swatch.bg-terrain-wasteland {
  background: var(--color-atlas-wasteland);
}
.design-sheet:not(.design-sheet--terminal) .biome-swatch.bg-terrain-forest {
  background: var(--color-atlas-forest);
}
.design-sheet:not(.design-sheet--terminal) .biome-swatch.bg-terrain-ruins {
  background: var(--color-atlas-ruins);
}
.design-sheet:not(.design-sheet--terminal) .biome-swatch.bg-terrain-hills {
  background: var(--color-atlas-hills);
}
.design-sheet:not(.design-sheet--terminal) .biome-swatch.bg-terrain-water {
  background: var(--color-atlas-water);
}
@media (max-width: 639px) {
  .design-sheet--atlas {
    @apply rounded-xl p-1;
  }
  .chart-title {
    @apply text-sm;
  }
  .chart-compass {
    @apply bottom-2 left-2;
  }
}
</style>
