<template>
  <Card class="mb-2 gap-0 rounded-lg border-2 border-theme-primary/20 p-6 shadow-none ring-0">
    <div class="grid grid-cols-1 md:grid-cols-[minmax(0,1fr)_14rem_auto] items-center gap-4">
      <!-- Parent names -->
      <div class="min-w-0">
        <div class="flex items-center gap-2 min-w-0">
          <DwellerPortrait
            :thumbnail-url="mother?.thumbnail_url"
            :alt="motherName"
            prefer-thumbnail
            image-class="h-8 w-8 shrink-0 rounded object-cover" fallback-class="h-8 w-8 shrink-0 text-theme-primary/60"
          />
          <span class="font-mono text-sm truncate">{{ motherName }}</span>
          <span class="shrink-0 text-pink-400">+</span>
          <span class="font-mono text-sm truncate">{{ fatherName }}</span>
          <DwellerPortrait
            :thumbnail-url="father?.thumbnail_url"
            :alt="fatherName"
            prefer-thumbnail
            image-class="h-8 w-8 shrink-0 rounded object-cover" fallback-class="h-8 w-8 shrink-0 text-theme-primary/60"
          />
        </div>

        <!-- Status badge -->
        <Badge :variant="badgeVariant" class="mt-1" :class="badgeClass">
          {{ pregnancy.status }}
        </Badge>
      </div>

      <!-- Progress bar (fixed column position) -->
      <div class="w-full md:w-56">
        <div
          class="flex items-center justify-between text-xs mb-1 text-theme-primary"
        >
          <span>Progress: {{ Math.round(pregnancy.progress_percentage) }}%</span>
          <span v-if="!pregnancy.is_due">{{ timeRemaining }}</span>
          <span v-else class="text-yellow-400 font-bold">DUE NOW!</span>
        </div>
        <div class="h-3 bg-black/80 border border-theme-primary/40 rounded-sm overflow-hidden">
          <div
            class="h-full rounded-sm transition-all duration-500"
            :class="pregnancy.is_due ? 'bg-yellow-500 animate-pulse' : ''"
            :style="{
              width: `${pregnancy.progress_percentage}%`,
              backgroundColor: pregnancy.is_due ? undefined : 'var(--color-theme-primary)',
            }"
          ></div>
        </div>
      </div>

      <!-- Deliver button -->
      <div class="flex justify-end">
        <Button
          v-if="pregnancy.is_due"
          variant="default"
          :disabled="isDelivering"
          class="animate-pulse border-2 border-theme-primary hover:shadow-glow-md"
          @click="$emit('deliver')"
        >
          {{ isDelivering ? 'Delivering...' : 'Deliver Baby' }}
        </Button>
      </div>
    </div>
  </Card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Pregnancy } from '../../models/pregnancy'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import { usePregnancyStore } from '../../stores/pregnancy'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import { Badge } from '@/core/components/ui/badge'
import { Button } from '@/core/components/ui/button'
import { Card } from '@/core/components/ui/card'

interface Props {
  pregnancy: Pregnancy
  mother?: DwellerShort | null
  father?: DwellerShort | null
  isDelivering?: boolean
}

const { isDelivering = false, father, mother, pregnancy } = defineProps<Props>()

defineEmits<{
  deliver: []
}>()

const pregnancyStore = usePregnancyStore()

/** Display name of the mother, falling back to "Unknown" when not loaded. */
const motherName = computed(() => formatDwellerName(mother))

/** Display name of the father, falling back to "Unknown" when not loaded. */
const fatherName = computed(() => formatDwellerName(father))

/** Format a dweller's full name, or "Unknown" when the dweller is absent. */
function formatDwellerName(dweller: DwellerShort | null | undefined): string {
  return dweller ? `${dweller.first_name} ${dweller.last_name ?? ''}`.trim() : 'Unknown'
}

/** Badge variant reflecting the pregnancy status and due state (shadcn names). */
const badgeVariant = computed((): 'default' | 'secondary' | 'destructive' | 'outline' => {
  switch (pregnancy.status) {
    case 'pregnant':
      return pregnancy.is_due ? 'outline' : 'default'
    case 'delivered':
      return 'outline'
    case 'miscarried':
      return 'destructive'
    default:
      return 'secondary'
  }
})

// `pregnant` + due has no shadcn amber equivalent; preserve its warning colour explicitly.
const badgeClass = computed(() =>
  pregnancy.status === 'pregnant' && pregnancy.is_due ? 'bg-warning text-black border-warning' : ''
)

/** Human-readable time remaining until the pregnancy is due. */
const timeRemaining = computed(() => {
  return pregnancyStore.formatTimeRemaining(pregnancy.time_remaining_seconds)
})
</script>
