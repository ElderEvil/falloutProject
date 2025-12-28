<script setup lang="ts">

import { useRoomInteractions } from '@/composables/useRoomInteractions'

const props = defineProps({
  room: {
    type: Object,
    required: true
  },
  isSelected: {
    type: Boolean,
    required: true
  }
})

const { toggleRoomSelection, destroyRoom } = useRoomInteractions()

const handleRoomClick = () => {
  toggleRoomSelection(props.room.id)
}

const handleDestroyClick = (event: Event) => {
  event.stopPropagation()
  destroyRoom(props.room.id, event)
}
</script>

<template>
  <div
    :style="{
      gridRow: props.room.coordinate_y + 1,
      gridColumn: `${props.room.coordinate_x + 1} / span ${Math.ceil(props.room.size / 3)}`
    }"
    class="room"
    :class="{ selected: isSelected }"
    @click="handleRoomClick"
  >
    <div class="room-content">
      <h3 class="room-name">{{ props.room.name }}</h3>
      <p class="room-category">{{ props.room.category }}</p>
      <button
        v-if="isSelected"
        @click="handleDestroyClick"
        class="destroy-button"
        title="Destroy Room"
      >
        <UIcon name="i-lucide-trash-2" />
      </button>
    </div>
  </div>
</template>
