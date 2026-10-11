<script setup lang="ts">
import { Icon } from '@iconify/vue'
import type { PlaceGroup } from '../models/map'
import { MARKER_TYPES } from '../models/markerTypeMeta'
import { DANGER_RAMP } from '../utils/dangerStyle'
import { groupColor } from '../models/groupColors'
import MapMarker from './MapMarker.vue'

withDefaults(defineProps<{ placeGroups?: PlaceGroup[]; groupColors?: boolean }>(), {
  placeGroups: () => [],
  groupColors: false,
})

const commonSymbols = [
  { type: 'explorer', icon: 'mdi:walk', label: 'Explorers / parties' },
  { type: 'cluster', icon: 'mdi:circle-multiple-outline', label: 'Grouped markers' },
]

const states = [
  { label: 'Locked', icon: 'mdi:lock-question' },
  { label: 'Cleared', icon: 'mdi:check' },
  { label: 'Cooldown', icon: 'mdi:clock-outline' },
  { label: 'Exploring', icon: 'mdi:circle-double' },
]
</script>

<template>
  <section
    class="map-legend border-b border-theme-primary/20 p-3 text-xs text-theme-primary"
    role="region"
    aria-label="Map legend"
  >
    <div class="grid grid-cols-2 gap-x-3 gap-y-2">
      <span v-for="symbol in commonSymbols" :key="symbol.type" class="flex items-center gap-1.5">
        <Icon :icon="symbol.icon" class="size-4 shrink-0" :ariaHidden="true" />
        {{ symbol.label }}
      </span>
    </div>
    <div class="legend-content mt-4 space-y-4">
      <section>
        <h3 class="mb-2 font-semibold">Marker symbols</h3>
        <div class="grid grid-cols-2 gap-x-3 gap-y-2">
          <span
            v-for="symbol in MARKER_TYPES"
            :key="symbol.type"
            class="legend-item flex items-center gap-1.5"
          >
            <Icon :icon="symbol.icon" class="size-4 shrink-0" :ariaHidden="true" />
            {{ symbol.label }}
          </span>
        </div>
        <p class="mt-2 leading-relaxed text-theme-primary/65">
          Place icons show type. Numbered markers group nearby places or parties.
        </p>
      </section>
      <section>
        <h3 class="mb-2 font-semibold">Place status</h3>
        <div class="grid grid-cols-2 gap-x-3 gap-y-2">
          <span
            v-for="state in states"
            :key="state.label"
            class="legend-item flex items-center gap-1.5"
          >
            <Icon :icon="state.icon" class="size-4 shrink-0" :ariaHidden="true" />
            {{ state.label }}
          </span>
        </div>
        <p class="mt-2 leading-relaxed text-theme-primary/65">
          Ready to clear: clearable now, with no party already dispatched.
        </p>
      </section>
      <section v-if="placeGroups.length">
        <h3 class="mb-2 font-semibold">Place types</h3>
        <div class="grid grid-cols-2 gap-x-3 gap-y-2">
          <span v-for="group in placeGroups" :key="group.key" class="flex items-center gap-1.5">
            <svg viewBox="-5 -5 10 10" class="size-5 shrink-0" aria-hidden="true">
              <MapMarker
                :x="0"
                :y="0"
                :name="group.label"
                type="discovery"
                :icon="group.icon"
                :color="groupColors ? groupColor(group.key) : null"
                :interactive="false"
              />
            </svg>
            {{ group.label }}
          </span>
        </div>
        <p class="mt-2 leading-relaxed text-theme-primary/65">
          Optional colors identify place type. Symbols show status.
        </p>
      </section>
      <section>
        <p class="leading-relaxed text-theme-primary/65">
          Risk: {{ DANGER_RAMP.map((entry) => entry.label).join(' · ') }}.
        </p>
        <p class="mt-2 leading-relaxed text-theme-primary/65">
          Fog marks unexplored terrain. Locked places hide their identity.
        </p>
      </section>
    </div>
  </section>
</template>
