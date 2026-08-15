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
  <div class="training-room-card" :class="occupancyTone">
    <div class="room-visual">
      <img v-if="roomImageUrl" :src="roomImageUrl" :alt="room.name" class="room-image" />
      <Icon v-else :icon="ability?.icon ?? 'mdi:star'" class="room-icon" />
    </div>

    <div class="room-body">
      <div class="room-header">
        <div class="room-title">
          <span class="room-name">{{ room.name }}</span>
          <span v-if="ability" class="room-ability">
            <Icon :icon="ability.icon" class="ability-icon" />
            {{ ability.letter }} - {{ ability.label }}
          </span>
        </div>
        <span class="tier-badge">T{{ room.tier }}</span>
      </div>

      <div class="occupancy">
        <div class="occupancy-header">
          <span class="occupancy-label">Occupancy</span>
          <span class="occupancy-value" :class="occupancyTone">{{ occupancyLabel }}</span>
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

<style scoped>
.training-room-card {
  display: flex;
  align-items: stretch;
  gap: 1rem;
  padding: 1rem;
  background: transparent;
  border: 2px solid var(--color-theme-primary);
  border-radius: 0.5rem;
  box-shadow: 0 0 10px var(--color-theme-glow);
  transition: all 0.2s ease;
}

.training-room-card:hover {
  border-color: var(--color-theme-accent);
  box-shadow: 0 0 15px var(--color-theme-accent);
}

.training-room-card.full {
  border-color: var(--color-danger);
  box-shadow: 0 0 10px rgb(255 0 0 / 0.4);
}

.training-room-card.busy {
  border-color: var(--color-warning);
  box-shadow: 0 0 10px rgb(255 170 0 / 0.4);
}

.room-visual {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 5rem;
  height: 5rem;
  border: 1px solid var(--color-theme-glow);
  border-radius: 0.375rem;
  background: rgb(0 0 0 / 0.3);
  overflow: hidden;
}

.room-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  image-rendering: pixelated;
}

.room-icon {
  font-size: 2.5rem;
  color: var(--color-theme-primary);
  filter: drop-shadow(0 0 4px var(--color-theme-glow));
}

.room-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  min-width: 0;
}

.room-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.5rem;
}

.room-title {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  min-width: 0;
}

.room-name {
  font-size: 0.875rem;
  font-weight: bold;
  color: var(--color-theme-primary);
  font-family: 'Courier New', monospace;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.room-ability {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  font-size: 0.75rem;
  color: var(--color-theme-primary);
  opacity: 0.7;
  font-family: 'Courier New', monospace;
}

.ability-icon {
  font-size: 0.875rem;
}

.tier-badge {
  flex-shrink: 0;
  padding: 0.125rem 0.5rem;
  border: 1px solid var(--color-theme-primary);
  border-radius: 0.25rem;
  font-size: 0.75rem;
  font-weight: bold;
  color: var(--color-theme-primary);
  font-family: 'Courier New', monospace;
}

.occupancy {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.occupancy-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.occupancy-label {
  font-size: 0.75rem;
  color: var(--color-theme-primary);
  opacity: 0.6;
  font-family: 'Courier New', monospace;
  text-transform: uppercase;
}

.occupancy-value {
  font-size: 0.75rem;
  font-weight: bold;
  color: var(--color-theme-primary);
  font-family: 'Courier New', monospace;
}

.occupancy-value.busy {
  color: var(--color-warning);
}

.occupancy-value.full {
  color: var(--color-danger);
}
</style>
