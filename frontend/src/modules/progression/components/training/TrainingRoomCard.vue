<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/core/components/ui/tooltip'
import type { Room } from '@/modules/rooms/models/room'
import { getTrainingRoomCapacity } from '@/modules/rooms/utils/room'

interface Props {
  room: Room
  vaultId: string
  activeCount: number
}

defineOptions({ inheritAttrs: false })

const props = defineProps<Props>()

// Room.capacity is null for training rooms (capacity_formula is null in room data).
// Fall back to the same formula RoomGrid uses: 2 dwellers per 3-tile segment.
const capacity = computed(() => getTrainingRoomCapacity(props.room))

const occupancySlots = computed(() =>
  Array.from({ length: capacity.value }, (_, index) => index < props.activeCount)
)

const occupancyLabel = computed(() => {
  if (capacity.value <= 0) return `${props.activeCount} training`
  return `${props.activeCount} / ${capacity.value}`
})
</script>

<template>
  <TooltipProvider>
    <Tooltip>
      <TooltipTrigger as-child>
        <RouterLink
          v-bind="$attrs"
          :to="{ path: `/vault/${vaultId}`, query: { roomId: room.id } }"
          :aria-label="`Open ${room.name}`"
          class="flex min-w-0 items-stretch rounded-lg border border-theme-primary bg-transparent p-2 shadow-[0_0_10px_var(--color-theme-glow)] transition-all duration-200 hover:border-theme-primary hover:shadow-[0_0_15px_var(--color-theme-glow)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-theme-primary"
        >
          <div class="flex min-w-0 flex-1 flex-col gap-2">
            <div class="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-x-2 gap-y-0.5">
              <span class="truncate font-mono text-xs font-bold text-theme-primary">{{
                room.name
              }}</span>
              <span
                class="shrink-0 rounded border border-theme-primary px-1.5 py-0.5 font-mono text-xs font-bold text-theme-primary"
                >T{{ room.tier }}</span
              >
            </div>

            <div
              class="flex items-center gap-2"
              :aria-label="`${occupancyLabel} training spaces occupied`"
              role="img"
            >
              <div class="flex min-w-0 flex-1 gap-1">
                <span
                  v-for="(isFilled, index) in occupancySlots"
                  :key="index"
                  class="occupancy-slot h-2 flex-1 rounded-sm border border-theme-primary/35"
                  :class="
                    isFilled
                      ? 'occupancy-slot--filled bg-theme-primary shadow-[0_0_6px_var(--color-theme-glow)]'
                      : 'bg-transparent'
                  "
                />
              </div>
              <span class="shrink-0 font-mono text-xs font-bold text-theme-primary">{{
                occupancyLabel
              }}</span>
            </div>
          </div>
        </RouterLink>
      </TooltipTrigger>
      <TooltipContent>Open {{ room.name }}</TooltipContent>
    </Tooltip>
  </TooltipProvider>
</template>
