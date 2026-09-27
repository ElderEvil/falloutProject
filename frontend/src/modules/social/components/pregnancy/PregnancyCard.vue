<script setup lang="ts">
import { computed } from 'vue'
import type { Pregnancy } from '../../models/pregnancy'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import { usePregnancyStore } from '../../stores/pregnancy'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import { Badge } from '@/core/components/ui/badge'
import { Button } from '@/core/components/ui/button'
import { Card } from '@/core/components/ui/card'
import { Progress } from '@/core/components/ui/progress'

interface Props {
  pregnancy: Pregnancy
  mother?: DwellerShort | null
  father?: DwellerShort | null
  isDelivering?: boolean
}

const props = withDefaults(defineProps<Props>(), { isDelivering: false })
defineEmits<{ deliver: [] }>()

const pregnancyStore = usePregnancyStore()
const parents = computed(() =>
  (
    [
      { role: 'Mother', dweller: props.mother },
      { role: 'Father', dweller: props.father },
    ] as const
  ).map(({ role, dweller }) => ({
    role,
    dweller,
    name: dweller ? `${dweller.first_name} ${dweller.last_name ?? ''}`.trim() : 'Unknown',
  }))
)
const progress = computed(() => Math.round(props.pregnancy.progress_percentage))
const timeRemaining = computed(() =>
  pregnancyStore.formatTimeRemaining(props.pregnancy.time_remaining_seconds)
)
</script>

<template>
  <Card
    class="h-full min-h-64 gap-0 rounded-lg border-2 border-theme-primary/20 p-4 shadow-none ring-0"
  >
    <div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
      <div
        v-for="parent in parents"
        :key="parent.role"
        class="flex min-h-20 min-w-0 items-center gap-2 rounded border border-theme-primary/20 bg-surface-sunken px-2 py-2"
      >
        <span
          class="flex size-14 shrink-0 items-center justify-center overflow-hidden rounded bg-black/30"
        >
          <DwellerPortrait
            :thumbnail-url="parent.dweller?.thumbnail_url"
            :alt="parent.name"
            prefer-thumbnail
            image-class="h-full w-full object-cover"
            fallback-class="h-9 w-9 text-theme-primary/60"
          />
        </span>
        <span class="min-w-0 flex-1">
          <span
            class="block text-[0.65rem] font-bold uppercase tracking-[0.08em] text-theme-primary/55"
          >
            {{ parent.role }}
          </span>
          <span class="block truncate text-sm font-bold text-theme-primary">{{ parent.name }}</span>
        </span>
      </div>
    </div>

    <div class="mt-3 rounded border border-theme-primary/20 bg-surface-sunken p-3">
      <div class="flex items-center justify-between gap-2 text-xs">
        <span class="font-bold tracking-[0.08em] text-theme-primary/60">BIRTH PROGRESS</span>
        <span class="font-bold text-theme-primary">{{ progress }}%</span>
      </div>
      <Progress
        :model-value="pregnancy.progress_percentage"
        :tone="pregnancy.is_due ? 'warning' : 'default'"
        label="Birth progress"
        :value-text="`${progress}% complete`"
        class="mt-2 h-2"
      />
      <p v-if="!pregnancy.is_due" class="mt-2 text-xs text-theme-primary/65">
        {{ timeRemaining }} remaining
      </p>
    </div>

    <div class="mt-auto flex items-center justify-between gap-2 pt-3">
      <Badge
        :variant="pregnancy.is_due ? 'outline' : 'secondary'"
        :class="pregnancy.is_due ? 'border-warning bg-warning text-black' : ''"
      >
        {{ pregnancy.is_due ? 'Due now' : 'Expecting' }}
      </Badge>
      <Button
        v-if="pregnancy.is_due"
        variant="default"
        :disabled="isDelivering"
        class="border-2 border-theme-primary hover:shadow-glow-md"
        @click="$emit('deliver')"
      >
        {{ isDelivering ? 'Delivering...' : 'Deliver Baby' }}
      </Button>
    </div>
  </Card>
</template>
