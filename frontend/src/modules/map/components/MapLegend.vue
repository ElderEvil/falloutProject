<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { MARKER_TYPES } from '../models/markerTypeMeta'
import { DANGER_RAMP } from '../utils/dangerStyle'
import {
  FAMILY_LABELS,
  FAMILY_MEANING,
  GROUP_FAMILIES,
  type GroupFamily,
} from '../models/groupColors'

withDefaults(defineProps<{ groupColors?: boolean }>(), {
  groupColors: true,
})

const familyKeys = Object.keys(GROUP_FAMILIES) as GroupFamily[]

const commonSymbols = [
  { type: 'explorer', icon: 'mdi:walk', label: 'Explorers / parties' },
  { type: 'cluster', icon: 'mdi:circle-multiple-outline', label: 'Grouped markers' },
]

const states = [
  { label: 'Unscouted', icon: 'mdi:map-marker-outline' },
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
          Place icons show type. Numbered markers group nearby places or parties. Vault signals are
          distant vaults, not destinations; selecting one shows its owner. Exhibition duels are
          arranged from your vault.
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
      <section v-if="groupColors">
        <h3 class="mb-2 font-semibold">Site families</h3>
        <div class="space-y-1.5">
          <span
            v-for="family in familyKeys"
            :key="family"
            class="legend-item flex items-baseline gap-1.5"
          >
            <svg viewBox="0 0 10 10" class="size-3 shrink-0 self-center" aria-hidden="true">
              <circle cx="5" cy="5" r="4.5" :style="{ fill: GROUP_FAMILIES[family] }" />
            </svg>
            <span class="font-medium">{{ FAMILY_LABELS[family] }}</span>
            <span class="text-theme-primary/65">{{ FAMILY_MEANING[family] }}</span>
          </span>
        </div>
        <p class="mt-2 leading-relaxed text-theme-primary/65">
          Colour shows the site family; the glyph shows the exact type. Unscouted places keep their
          family colour, dimmed and ringed.
        </p>
      </section>
      <section>
        <p class="leading-relaxed text-theme-primary/65">
          Risk: {{ DANGER_RAMP.map((entry) => entry.label).join(' · ') }}.
        </p>
        <p class="mt-2 leading-relaxed text-theme-primary/65">
          Fog marks unexplored terrain. Unscouted places wear a neutral pin and a dashed ring,
          though their colour still hints at the family.
        </p>
      </section>
    </div>
  </section>
</template>
