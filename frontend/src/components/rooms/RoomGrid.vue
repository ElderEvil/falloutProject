<script setup lang="ts">
import { computed } from 'vue'
import { useRoomStore } from '@/stores/room'
import { useAuthStore } from '@/stores/auth'
import { useRoomInteractions } from '@/composables/useRoomInteractions'
import { useHoverPreview } from '@/composables/useHoverPreview'
import { TrashIcon } from '@heroicons/vue/24/solid'

const roomStore = useRoomStore()
const authStore = useAuthStore()
const rooms = computed(() => roomStore.rooms)

const { selectedRoomId, toggleRoomSelection, destroyRoom } = useRoomInteractions()
const { hoverPosition, handleHover, clearHover, previewCells, isValidPlacement } = useHoverPreview()

const placeRoom = async (x: number, y: number) => {
  if (roomStore.selectedRoom && roomStore.isPlacingRoom) {
    const roomSize = roomStore.selectedRoom.size
    const placementX = roomSize <= 3 ? x : x - Math.floor(roomSize / 6)
    await roomStore.buildRoom(
      {
        coordinate_x: placementX,
        coordinate_y: y,
        type: roomStore.selectedRoom.category
      },
      authStore.token as string
    )
    roomStore.deselectRoom()
  }
}
</script>

<template>
  <div class="room-grid">
    <div
      v-for="room in rooms"
      :key="room.id"
      :style="{
        gridRow: room.coordinate_y + 1,
        gridColumn: `${room.coordinate_x + 1} / span ${Math.ceil(room.size / 3)}`
      }"
      class="room"
      :class="{ selected: selectedRoomId === room.id }"
      @click="toggleRoomSelection(room.id)"
    >
      <div class="room-content">
        <h3 class="room-number">{{ room.number }}</h3>
        <p class="room-category">{{ room.category }}</p>
        <button
          v-if="selectedRoomId === room.id"
          @click="destroyRoom(room.id, $event)"
          class="destroy-button"
          title="Destroy Room"
        >
          <TrashIcon />
        </button>
      </div>
    </div>
    <div
      v-for="n in 25 * 8"
      :key="'empty-' + n"
      class="room empty"
      :class="{
        'hover-preview': previewCells.some(
          (cell) => cell.x === n % 8 && cell.y === Math.floor(n / 8)
        ),
        'valid-placement': isValidPlacement && hoverPosition,
        'invalid-placement': hoverPosition && !isValidPlacement
      }"
      :data-cell-info="`x:${n % 8}, y:${Math.floor(n / 8)}, preview:${previewCells.some(
        (cell) => cell.x === n % 8 && cell.y === Math.floor(n / 8)
      )}, valid:${isValidPlacement}`"
      @mouseenter="handleHover(n % 8, Math.floor(n / 8))"
      @mouseleave="clearHover"
    ></div>
  </div>
</template>

<style scoped>
.room-grid {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 10px;
}

.room {
  position: relative;
  background-color: #333;
  border: 1px solid #555;
  cursor: pointer;
  transition: transform 0.2s;
}

.room.selected {
  border-color: #00ff00;
  transform: scale(1.05);
}

.room-content {
  padding: 10px;
  text-align: center;
}

.room-number {
  font-size: 1.2em;
  margin-bottom: 5px;
}

.room-category {
  font-size: 0.9em;
  color: #aaa;
}

.destroy-button {
  position: absolute;
  top: 5px;
  right: 5px;
  background: none;
  border: none;
  cursor: pointer;
  color: #ff0000;
}

.empty {
  border: 1px dashed #555;
  background-color: rgba(0, 0, 0, 0.3);
  aspect-ratio: 2 / 1;
}

.hover-preview {
  background-color: rgba(0, 255, 0, 0.3);
  z-index: 1;
}

.valid-placement .hover-preview {
  background-color: transparent;
  background-image: linear-gradient(
    45deg,
    rgba(0, 255, 0, 0.5) 25%,
    transparent 25%,
    transparent 50%,
    rgba(0, 255, 0, 0.5) 50%,
    rgba(0, 255, 0, 0.5) 75%,
    transparent 75%,
    transparent
  );
  background-size: 20px 20px;
  border: 2px solid #00ff00;
}

.invalid-placement .hover-preview {
  background-color: transparent;
  background-image: linear-gradient(
    45deg,
    rgba(255, 0, 0, 0.5) 25%,
    transparent 25%,
    transparent 50%,
    rgba(255, 0, 0, 0.5) 50%,
    rgba(255, 0, 0, 0.5) 75%,
    transparent 75%,
    transparent
  );
  background-size: 20px 20px;
  border: 2px solid #ff0000;
}
</style>
