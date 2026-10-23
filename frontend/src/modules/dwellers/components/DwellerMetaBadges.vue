<script setup lang="ts">
import type { DwellerShort } from '../models/dweller'
import DwellerAgeBadge from './DwellerAgeBadge.vue'
import DwellerGenderBadge from './DwellerGenderBadge.vue'
import DwellerRarityBadge from './DwellerRarityBadge.vue'
import DwellerIdentitySignal from './DwellerIdentitySignal.vue'

withDefaults(
  defineProps<{
    dweller: DwellerShort
    showIdentity?: boolean
  }>(),
  { showIdentity: false }
)
</script>

<template>
  <span class="dweller-meta-badges flex flex-wrap items-center gap-1.5">
    <DwellerAgeBadge :age-group="dweller.age_group" size="sm" />
    <DwellerGenderBadge :gender="dweller.gender" size="sm" />
    <DwellerRarityBadge :rarity="dweller.rarity" size="sm" />
    <DwellerIdentitySignal
      v-if="showIdentity"
      :visual-attributes="dweller.visual_attributes"
      compact
    />
  </span>
</template>
