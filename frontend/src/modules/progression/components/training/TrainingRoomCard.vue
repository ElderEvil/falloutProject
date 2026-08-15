<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import UProgressBar from '@/core/components/ui/UProgressBar.vue'
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

const occupancyPercent = computed(() => {
  if (capacity.value <= 0) return 0
  return Math.min(100, Math.round((props.activeCount / capacity.value) * 100))
})

const isFull = computed(() => capacity.value > 0 && props.activeCount >= capacity.value)

const occupancyTone = computed(() => {
  if (isFull.value) return 'full'
  if (occupancyPercent.value >= 75) return 'busy'
  return 'ok'
})

const barColor = computed(() => {
  switch (occupancyTone.value) {
    case 'full':
      return 'linear-gradient(to right, var(--color-danger), var(--color-warning))'
    case 'busy':
      return 'linear-gradient(to right, var(--color-warning), var(--color-warning))'
    default:
      return 'linear-gradient(to right, var(--color-theme-primary), var(--color-theme-accent))'
  }
})

const roomImageUrl = computed(() => getRoomImageUrl(props.room.image_url))

const occupancyLabel = computed(() => {
  if (capacity.value <= 0) return `${props.activeCount} training`
  if (isFull.value) return 'Full'
  return `${props.activeCount} / ${capacity.value}`
})
</script>

<template>
  <div
    class="flex items-stretch gap-4 rounded-lg border-2 border-theme-primary bg-transparent p-4 shadow-[0_0_10px_var(--color-theme-glow)] transition-all duration-200"
    :class="{
      'hover:border-theme-accent hover:shadow-[0_0_15px_var(--color-theme-accent)]':
        occupancyTone === 'ok',
      'border-danger shadow-[0_0_10px_rgb(255_0_0_/_0.4)]': occupancyTone === 'full',
      'border-warning shadow-[0_0_10px_rgb(255_170_0_/_0.4)]': occupancyTone === 'busy',
    }"
  >
    <div
      class="flex h-20 w-20 shrink-0 items-center justify-center overflow-hidden rounded-md border border-theme-glow bg-black/30"
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
        class="text-4xl text-theme-primary [filter:drop-shadow(0_0_4px_var(--color-theme-glow))]"
      />
    </div>

    <div class="flex min-w-0 flex-1 flex-col gap-3">
      <div class="flex items-start justify-between gap-2">
        <div class="flex min-w-0 flex-col gap-1">
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
          class="shrink-0 rounded border border-theme-primary px-2 py-0.5 font-mono text-xs font-bold text-theme-primary"
          >T{{ room.tier }}</span
        >
      </div>

      <div class="flex flex-col gap-1.5">
        <div class="flex items-center justify-between">
          <span class="font-mono text-xs uppercase text-theme-primary opacity-60">Occupancy</span>
          <span
            class="font-mono text-xs font-bold text-theme-primary"
            :class="{
              'text-warning': occupancyTone === 'busy',
              'text-danger': occupancyTone === 'full',
            }"
            >{{ occupancyLabel }}</span
          >
        </div>
        <UProgressBar
          :model-value="occupancyPercent"
          :height="10"
          :color="barColor"
          :glow="false"
        />
      </div>
    </div>
  </div>
</template>
