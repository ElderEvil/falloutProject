<script setup lang="ts">
import { ref } from 'vue'
import { Button } from '@/core/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/core/components/ui/card'
import { useMapStore } from '@/modules/map/stores/map'
import {
  ANCHOR_CONSTRAINT_VERSION,
  HOURS_PER_COST,
  ROAD_TRAVEL_DISCOUNT,
  SHARED_ANCHOR_FIXTURES,
  SHARED_FIXTURE_VERSION,
  findPath,
  generateWorld,
  type AnchorDiagnostic,
  type GeneratedWorld,
  type TerrainAnchor,
} from '@/modules/map/utils/atlasWorldgen'
import { scoutBand } from './scout'

interface WorldReport {
  label: string
  anchors: number
  conflicts: number
  moved: number
  unreachable: number
}

const mapStore = useMapStore()
const reports = ref<WorldReport[] | null>(null)
const realAnchorCount = ref(0)
const travel = ref<{ reachable: number; total: number; changed: number; band: string } | null>(null)

function summarize(label: string, diagnostics: AnchorDiagnostic[]): WorldReport {
  let conflicts = 0
  let moved = 0
  let unreachable = 0
  for (const d of diagnostics) {
    if (d.conflict !== null) conflicts++
    if (d.before !== null && d.after !== null && d.before !== d.after) moved++
    if (d.before !== null && !d.reachable) unreachable++
  }
  return { label, anchors: diagnostics.length, conflicts, moved, unreachable }
}

/** Read-only travel evaluation: how far the real anchors are, and whether the road
 *  discount changes their cost. Authoritative travel stays gated. */
function evaluateTravel(world: GeneratedWorld, tiles: Array<{ x: number; y: number }>): void {
  let reachable = 0
  let changed = 0
  let sumPlain = 0
  for (const tile of tiles) {
    const plain = findPath(world, world.origin, tile)
    if (plain === null) continue
    reachable++
    sumPlain += plain.cost
    const discounted = findPath(world, world.origin, tile, { roadDiscount: ROAD_TRAVEL_DISCOUNT })
    if (discounted !== null && discounted.cost !== plain.cost) changed++
  }
  const avgHours = reachable > 0 ? Math.round((sumPlain / reachable) * HOURS_PER_COST) : 0
  const band = scoutBand(avgHours)
  travel.value = { reachable, total: tiles.length, changed, band: `~${band.low}–${band.high} h` }
}

const run = (): void => {
  // Real public anchors: seeded vault signals from the existing map read. The API
  // returns these scaled/rounded, so they are approximate — a mapping diagnostic,
  // not exact registry anchors.
  const realAnchors: TerrainAnchor[] = mapStore.vaultMarkers.map((marker, i) => ({
    id: `seed-vault-${i}`,
    name: marker.name,
    coord_x: marker.coord_x,
    coord_y: marker.coord_y,
    terrain: 'wasteland',
  }))
  realAnchorCount.value = realAnchors.length

  // World 1: exact synthetic fixtures only (deterministic, version-pinned).
  // World 2: fixtures + real public anchors, through the same constraint pass.
  const fixtureWorld = generateWorld(undefined, SHARED_ANCHOR_FIXTURES)
  const mergedWorld = generateWorld(undefined, [...SHARED_ANCHOR_FIXTURES, ...realAnchors])

  reports.value = [
    summarize('Synthetic fixtures only', fixtureWorld.anchorDiagnostics),
    summarize('Fixtures + real public anchors', mergedWorld.anchorDiagnostics),
  ]

  const realTiles = mergedWorld.anchorDiagnostics
    .filter(d => d.anchor.id.startsWith('seed-vault-'))
    .map(d => ({ x: d.x, y: d.y }))
  evaluateTravel(mergedWorld, realTiles)
}
</script>

<template>
  <Card class="mt-4 border-dashed border-theme-primary/40">
    <CardHeader>
      <CardTitle class="text-sm">DEV · Anchored-geography diagnostic (read-only)</CardTitle>
    </CardHeader>
    <CardContent class="flex flex-col gap-2 text-xs text-theme-primary/80">
      <p class="text-theme-primary/60">
        Evaluates Option A on two worlds through one versioned constraint pass: exact
        synthetic fixtures, and fixtures merged with this vault's real public anchors
        (seeded vault signals). Changes no production state.
      </p>
      <p class="text-theme-primary/40">
        constraint v{{ ANCHOR_CONSTRAINT_VERSION }} · fixtures {{ SHARED_FIXTURE_VERSION }}
      </p>
      <Button variant="outline" size="sm" class="w-fit" @click="run">Run evaluation</Button>
      <ul v-if="reports" class="flex flex-col gap-2">
        <li v-for="report in reports" :key="report.label" class="flex flex-col">
          <span class="text-theme-primary">{{ report.label }}</span>
          <span>
            anchors {{ report.anchors }} · conflicts {{ report.conflicts }} · terrain moved
            {{ report.moved }} · unreachable {{ report.unreachable }}
          </span>
        </li>
        <li class="text-theme-primary/50">
          Real anchors: {{ realAnchorCount }} (scaled/rounded by the API). Mapping diagnostic
          only — projection does not establish terrain compatibility.
        </li>
        <li v-if="travel" class="text-theme-primary/70">
          Travel (real anchors): {{ travel.reachable }}/{{ travel.total }} reachable · road
          discount changes {{ travel.changed }} · coarse band {{ travel.band }}
        </li>
      </ul>
      <p v-else class="text-theme-primary/40">No evaluation yet.</p>
    </CardContent>
  </Card>
</template>
