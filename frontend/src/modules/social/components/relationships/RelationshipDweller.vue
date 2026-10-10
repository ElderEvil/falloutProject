<script setup lang="ts">
import { computed } from 'vue'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import DwellerGenderBadge from '@/modules/dwellers/components/DwellerGenderBadge.vue'
import DwellerRaceBadge from '@/modules/dwellers/components/DwellerRaceBadge.vue'

const props = defineProps<{ dweller: DwellerShort }>()
const emit = defineEmits<{ select: [dwellerId: string] }>()

const fullName = computed(() =>
  `${props.dweller.first_name} ${props.dweller.last_name ?? ''}`.trim()
)
</script>

<template>
  <button
    type="button"
    :title="`View ${fullName}`"
    class="group flex min-h-28 min-w-0 items-center gap-2 rounded border border-theme-primary/20 bg-surface-sunken px-2 py-2 text-left transition-colors hover:border-theme-primary/60 hover:bg-surface-hover focus:outline-none focus:ring-2 focus:ring-theme-primary/50"
    @click="emit('select', dweller.id)"
  >
    <span
      class="dweller-portrait-frame flex size-16 shrink-0 items-center justify-center overflow-hidden rounded bg-black/30"
    >
      <DwellerPortrait
        :thumbnail-url="dweller.thumbnail_url"
        :alt="fullName"
        prefer-thumbnail
        image-class="h-full w-full object-cover"
        fallback-class="h-10 w-10 text-theme-primary/60"
      />
    </span>
    <span class="flex min-w-0 flex-1 flex-col items-start gap-1">
      <span
        class="block w-full truncate text-sm font-bold text-theme-primary"
        >{{ fullName }}</span
      >
      <span class="flex w-full flex-wrap items-center gap-1">
        <DwellerRaceBadge :race="dweller.visual_attributes?.race ?? 'human'" show-label size="sm" />
        <DwellerGenderBadge :gender="dweller.gender" size="sm" />
      </span>
      <span class="text-[0.65rem] font-bold text-theme-primary/65" title="Charisma"
        >C {{ dweller.charisma }}</span
      >
    </span>
  </button>
</template>
