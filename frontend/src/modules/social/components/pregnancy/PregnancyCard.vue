<template>
  <UCard class="mb-2">
    <div class="grid grid-cols-1 md:grid-cols-[minmax(0,1fr)_14rem_auto] items-center gap-4">
      <!-- Parent names -->
      <div class="min-w-0">
        <div class="flex items-center gap-2 min-w-0">
          <DwellerPortrait
            :thumbnail-url="mother?.thumbnail_url"
            :alt="motherName"
            prefer-thumbnail
            image-class="h-8 w-8 shrink-0 rounded object-cover"
          />
          <span class="font-mono text-sm truncate">{{ motherName }}</span>
          <span class="shrink-0 text-pink-400">+</span>
          <span class="font-mono text-sm truncate">{{ fatherName }}</span>
          <DwellerPortrait
            :thumbnail-url="father?.thumbnail_url"
            :alt="fatherName"
            prefer-thumbnail
            image-class="h-8 w-8 shrink-0 rounded object-cover"
          />
        </div>

        <!-- Status badge -->
        <UBadge :variant="statusColor" class="mt-1">
          {{ pregnancy.status }}
        </UBadge>
      </div>

      <!-- Progress bar (fixed column position) -->
      <div class="w-full md:w-56">
        <div
          class="flex items-center justify-between text-xs mb-1"
          :style="{ color: 'var(--color-theme-primary)' }"
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
        <UButton
          v-if="pregnancy.is_due"
          @click="$emit('deliver')"
          :disabled="isDelivering"
          class="animate-pulse"
        >
          {{ isDelivering ? 'Delivering...' : 'Deliver Baby' }}
        </UButton>
      </div>
    </div>
  </UCard>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Pregnancy } from '../../models/pregnancy'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import { usePregnancyStore } from '../../stores/pregnancy'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import UCard from '@/core/components/ui/UCard.vue'
import UBadge from '@/core/components/ui/UBadge.vue'
import UButton from '@/core/components/ui/UButton.vue'

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

/** Badge variant reflecting the pregnancy status and due state. */
const statusColor = computed((): 'success' | 'warning' | 'danger' | 'info' | 'default' => {
  switch (pregnancy.status) {
    case 'pregnant':
      return pregnancy.is_due ? 'warning' : 'success'
    case 'delivered':
      return 'info'
    case 'miscarried':
      return 'danger'
    default:
      return 'default'
  }
})

/** Human-readable time remaining until the pregnancy is due. */
const timeRemaining = computed(() => {
  return pregnancyStore.formatTimeRemaining(pregnancy.time_remaining_seconds)
})
</script>
