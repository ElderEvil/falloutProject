<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { useRoomInteractions } from '../composables/useRoomInteractions'

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

const roomImageUrl = computed(() => {
  if (!props.room.image_url) return null
  const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
  return `${baseUrl}${props.room.image_url}`
})

const handleRoomClick = () => {
  toggleRoomSelection(props.room.id)
}

const handleDestroyClick = (event: MouseEvent) => {
  event.stopPropagation()
  destroyRoom(props.room.id, event)
}
</script>

<template>
  <div
    :style="{
      gridRow: props.room.coordinate_y + 1,
      gridColumn: `${props.room.coordinate_x + 1} / span ${Math.ceil(props.room.size / 3)}`,
      backgroundImage: roomImageUrl ? `url(${roomImageUrl})` : 'none',
      backgroundSize: 'cover',
      backgroundPosition: 'center',
      backgroundRepeat: 'no-repeat'
    }"
    class="room"
    :class="{ selected: isSelected, 'has-image': roomImageUrl }"
    @click="handleRoomClick"
  >
    <div class="room-overlay"></div>
    <div class="room-content">
      <h3 class="room-name">{{ props.room.name }}</h3>
      <p class="room-category">{{ props.room.category }}</p>
      <p v-if="props.room.tier" class="room-tier">Tier {{ props.room.tier }}</p>
      <button
        v-if="isSelected"
        @click="handleDestroyClick"
        class="destroy-button"
        title="Destroy Room"
      >
        <Icon icon="mdi:delete" class="h-5 w-5" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.room {
  position: relative;
  overflow: hidden;
}

.room.has-image {
  /* Enhance contrast for rooms with background images */
  color: #00ff00;
  text-shadow: 0 0 4px rgba(0, 0, 0, 0.8), 0 0 8px rgba(0, 255, 0, 0.5);
}

.room-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    to bottom,
    rgba(0, 0, 0, 0.3) 0%,
    rgba(0, 0, 0, 0.5) 100%
  );
  pointer-events: none;
  z-index: 1;
}

.room-content {
  position: relative;
  z-index: 2;
  padding: 0.5rem;
}

.room-tier {
  font-size: 0.75rem;
  opacity: 0.8;
  margin-top: 0.25rem;
}
</style>
