<script setup lang="ts">
import { Icon } from '@iconify/vue'
import {
  getDwellerDisplayName,
  type DwellerShort,
  type Dweller,
} from '@/modules/dwellers/models/dweller'
import DwellerIdentitySignal from '@/modules/dwellers/components/DwellerIdentitySignal.vue'
import DwellerAgeBadge from '@/modules/dwellers/components/DwellerAgeBadge.vue'
import DwellerGenderBadge from '@/modules/dwellers/components/DwellerGenderBadge.vue'
import DwellerRarityBadge from '@/modules/dwellers/components/DwellerRarityBadge.vue'

defineProps<{ members: (DwellerShort | Dweller)[] }>()
</script>

<template>
  <div class="party-section grid gap-2 border-t border-theme-primary/20 pt-3">
    <div
      class="party-header flex items-center justify-between gap-3 text-xs uppercase tracking-wide text-theme-primary/80"
    >
      <span>Team</span>
      <span>{{ members.length }} / 3 assigned</span>
    </div>
    <div class="party-members grid gap-1.5">
      <div
        v-for="member in members"
        :key="member.id"
        class="party-member flex min-w-0 items-center gap-2 text-sm text-theme-primary"
      >
        <Icon icon="mdi:account" class="member-icon size-4 shrink-0 text-theme-accent" />
        <div class="member-info grid min-w-0 gap-0.5">
          <span class="member-name truncate">{{ getDwellerDisplayName(member) }}</span>
          <div class="member-badges flex flex-wrap items-center gap-1">
            <DwellerAgeBadge :age-group="member.age_group" size="sm" />
            <DwellerGenderBadge :gender="member.gender" size="sm" />
            <DwellerRarityBadge :rarity="member.rarity" size="sm" />
            <DwellerIdentitySignal :visual-attributes="member.visual_attributes" compact />
          </div>
        </div>
        <span class="member-level ml-auto shrink-0 text-xs text-theme-accent"
          >Lv.{{ member.level }}</span
        >
      </div>
      <p v-if="!members.length" class="text-xs text-theme-primary/70">Party roster unavailable.</p>
    </div>
  </div>
</template>
