<script setup lang="ts">
import { computed } from 'vue'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import DwellerAgeBadge from '@/modules/dwellers/components/DwellerAgeBadge.vue'
import DwellerGenderBadge from '@/modules/dwellers/components/DwellerGenderBadge.vue'
import DwellerRarityBadge from '@/modules/dwellers/components/DwellerRarityBadge.vue'

interface Props {
  dweller: DwellerShort
}

const props = defineProps<Props>()

const emit = defineEmits<{ (e: 'select', dwellerId: string): void }>()

const fullName = computed(() =>
  `${props.dweller.first_name} ${props.dweller.last_name ?? ''}`.trim()
)

const specialStats = computed(() => [
  { letter: 'S', value: props.dweller.strength },
  { letter: 'P', value: props.dweller.perception },
  { letter: 'E', value: props.dweller.endurance },
  { letter: 'C', value: props.dweller.charisma },
  { letter: 'I', value: props.dweller.intelligence },
  { letter: 'A', value: props.dweller.agility },
  { letter: 'L', value: props.dweller.luck },
])
</script>

<template>
  <button
    type="button"
    class="flex flex-col gap-2 rounded border border-theme-primary/20 bg-surface-sunken p-3 text-left transition-all hover:border-theme-primary/50 hover:bg-surface-hover"
    @click="emit('select', dweller.id)"
  >
    <div class="flex items-center gap-3">
      <DwellerPortrait
        :thumbnail-url="dweller.thumbnail_url"
        :alt="fullName"
        prefer-thumbnail
        image-class="h-10 w-10 rounded object-cover"
        fallback-class="h-10 w-10 text-theme-primary/60"
      />
      <div class="min-w-0 flex-1">
        <p class="truncate text-sm font-bold text-theme-primary">{{ fullName }}</p>
        <div class="mt-1 flex flex-wrap items-center gap-1">
          <DwellerAgeBadge :age-group="dweller.age_group" size="sm" />
          <DwellerGenderBadge :gender="dweller.gender" size="sm" />
          <DwellerRarityBadge :rarity="dweller.rarity" size="sm" />
        </div>
      </div>
    </div>

    <p class="text-xs text-theme-primary/70">
      HP {{ dweller.health }}/{{ dweller.max_health }} · Happy {{ dweller.happiness }}%
    </p>

    <div class="flex justify-between gap-1 border-t border-theme-primary/20 pt-2">
      <div
        v-for="stat in specialStats"
        :key="stat.letter"
        class="stat-mini flex flex-col items-center gap-0.5"
      >
        <span class="stat-letter text-[0.625rem] font-bold text-theme-primary/60">
          {{ stat.letter }}
        </span>
        <span class="stat-value text-xs font-bold text-theme-primary">{{ stat.value }}</span>
      </div>
    </div>
  </button>
</template>
