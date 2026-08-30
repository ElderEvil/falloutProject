<script setup lang="ts">
import type { DwellerShort } from '../models/dweller'
import DwellerPortrait from './DwellerPortrait.vue'
import DwellerAgeBadge from './DwellerAgeBadge.vue'
import DwellerGenderBadge from './DwellerGenderBadge.vue'
import DwellerRarityBadge from './DwellerRarityBadge.vue'

interface Props {
  dweller: DwellerShort
  /** Whether clicking/keyboard-activating the row emits `activate`. */
  clickable?: boolean
}

const { clickable = true, dweller } = defineProps<Props>()

const emit = defineEmits<{
  (e: 'activate', dwellerId: string): void
}>()

function activate() {
  if (clickable) emit('activate', dweller.id)
}
</script>

<template>
  <li
    class="flex items-center gap-3 rounded border border-theme-primary/20 bg-surface-canvas p-3 transition-all hover:bg-surface-hover"
    :class="clickable ? 'cursor-pointer' : ''"
    :role="clickable ? 'button' : undefined"
    :tabindex="clickable ? 0 : undefined"
    @click="activate"
    @keydown.enter.prevent="activate"
    @keydown.space.prevent="activate"
  >
    <div class="flex-shrink-0">
      <DwellerPortrait
        :thumbnail-url="dweller.thumbnail_url"
        alt=""
        url-mode="static"
        fallback-icon="mdi:account-circle"
        image-class="h-16 w-16 rounded object-cover"
        fallback-class="h-16 w-16 text-theme-primary/60"
      />
    </div>

    <div class="dweller-identity flex w-44 min-w-0 flex-col">
      <h3 class="truncate text-base font-bold text-terminal-green">
        {{ dweller.first_name }} {{ dweller.last_name }}
      </h3>
      <div class="flex items-center gap-2">
        <p class="text-sm text-theme-primary/60">Level {{ dweller.level }}</p>
        <DwellerAgeBadge :age-group="dweller.age_group" size="sm" />
        <DwellerGenderBadge :gender="dweller.gender" size="sm" />
        <DwellerRarityBadge :rarity="dweller.rarity" size="sm" />
      </div>
    </div>

    <!-- Row-specific sections (status, stats, indicators, ...) -->
    <slot name="middle" />

    <div class="ml-auto flex items-center gap-2">
      <slot name="actions" />
    </div>
  </li>
</template>
