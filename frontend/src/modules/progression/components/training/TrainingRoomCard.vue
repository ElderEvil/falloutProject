<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import type { Room } from '@/modules/rooms/models/room'
import { getAbilityConfig } from '@/modules/dwellers/models/dweller'
import { getRoomImageUrl } from '@/core/utils/image'
import { getTrainingRoomCapacity } from '@/modules/rooms/utils/room'

interface Props {
  room: Room
  activeCount: number
}

const props = defineProps<Props>()

const ability = computed(() => getAbilityConfig(props.room.ability))

// Room.capacity is null for training rooms (capacity_formula is null in room data).
// Fall back to the same formula RoomGrid uses: 2 dwellers per 3-tile segment.
const capacity = computed(() => getTrainingRoomCapacity(props.room))

const occupancySlots = computed(() =>
  Array.from({ length: capacity.value }, (_, index) => index < props.activeCount)
)

const roomImageUrl = computed(() => getRoomImageUrl(props.room.image_url))

const occupancyLabel = computed(() => {
  if (capacity.value <= 0) return `${props.activeCount} training`
  return `${props.activeCount} / ${capacity.value}`
})
</script>

<template>
  <div
    class="flex items-stretch gap-3 rounded-lg border-2 border-theme-primary bg-transparent p-3 shadow-[0_0_10px_var(--color-theme-glow)] transition-all duration-200 hover:border-theme-primary hover:shadow-[0_0_15px_var(--color-theme-glow)]"
  >
    <div
      class="flex h-14 w-14 shrink-0 items-center justify-center overflow-hidden rounded-md border border-theme-glow bg-black/30"
    >
      <img
        v-if="roomImageUrl"
        :src="roomImageUrl"
        :alt="room.name"
        class="h-full w-full object-cover [image-rendering:pixelated]"
      />
      <Icon
        v-else
        :icon="ability?.icon ?? 'mdi:star'"
        class="text-3xl text-theme-primary [filter:drop-shadow(0_0_4px_var(--color-theme-glow))]"
      />
    </div>

    <div class="flex min-w-0 flex-1 flex-col gap-2">
      <div class="flex items-start justify-between gap-2">
        <div class="flex min-w-0 flex-col gap-0.5">
          <span
            class="truncate font-mono text-sm font-bold uppercase tracking-[0.05em] text-theme-primary"
            >{{ room.name }}</span
          >
          <span
            v-if="ability"
            class="flex items-center gap-1.5 font-mono text-xs text-theme-primary opacity-70"
          >
            <Icon :icon="ability.icon" class="text-sm" />
            {{ ability.letter }} - {{ ability.label }}
          </span>
        </div>
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
            :class="isFilled ? 'occupancy-slot--filled bg-theme-primary shadow-[0_0_6px_var(--color-theme-glow)]' : 'bg-transparent'"
          />
        </div>
        <span class="shrink-0 font-mono text-xs font-bold text-theme-primary">{{
          occupancyLabel
        }}</span>
      </div>
    </div>
  </div>
</template>
