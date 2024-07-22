<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoomStore } from '@/stores/room'
import { useAuthStore } from '@/stores/auth'
import DestroyIcon from '@/components/icons/DestroyButton.vue'

interface Room {
  id: string
  name: string
  category: string
  coordinate_x: number
  coordinate_y: number
  size: number
}

const roomStore = useRoomStore()
const authStore = useAuthStore()
const rooms = computed(() => roomStore.rooms)
const selectedRoomId = ref<string | null>(null)
const hoverPosition = ref<{ x: number; y: number } | null>(null)

const toggleRoomSelection = (roomId: string) => {
  selectedRoomId.value = selectedRoomId.value === roomId ? null : roomId
}

const destroyRoom = async (roomId: string, event: Event) => {
  event.stopPropagation()
  if (confirm('Are you sure you want to destroy this room?')) {
    await roomStore.destroyRoom(roomId, authStore.token as string)
    selectedRoomId.value = null
  }
}

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

const handleHover = (x: number, y: number) => {
  if (roomStore.selectedRoom && roomStore.isPlacingRoom) {
    hoverPosition.value = { x, y }
  } else {
    hoverPosition.value = null
  }
}

const clearHover = () => {
  hoverPosition.value = null
}

const previewCells = computed(() => {
  if (!hoverPosition.value || !roomStore.selectedRoom) return []
  const { x, y } = hoverPosition.value
  const roomSize = roomStore.selectedRoom.size
  const cellsCount = Math.ceil(roomSize / 3)
  const startX = roomSize <= 3 ? x : x - Math.floor(cellsCount / 2)
  return Array.from({ length: cellsCount }, (_, i) => ({ x: startX + i, y }))
})

const isValidPlacement = computed(() => {
  if (!hoverPosition.value || !roomStore.selectedRoom) return false
  return previewCells.value.every(
    (cell) =>
      cell.x >= 0 &&
      cell.x < 8 &&
      !rooms.value.some(
        (room) =>
          room.coordinate_x <= cell.x &&
          room.coordinate_x + Math.ceil(room.size / 3) > cell.x &&
          room.coordinate_y === cell.y
      )
  )
})
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
        <h3 class="room-name">{{ room.name }}</h3>
        <p class="room-category">{{ room.category }}</p>
        <button
          v-if="selectedRoomId === room.id"
          @click="destroyRoom(room.id, $event)"
          class="destroy-button"
          title="Destroy Room"
        >
          <DestroyIcon />
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
        'valid-placement': isValidPlacement,
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
  grid-template-rows: repeat(25, 1fr);
  gap: 2px;
  position: relative;
  max-width: 100%;
}

.room {
  border: 1px solid #00ff00;
  background-color: rgba(0, 0, 0, 0.5);
  text-align: center;
  transition:
    transform 0.3s,
    background-color 0.3s;
  cursor: pointer;
}

.room:hover {
  transform: scale(1.05);
}

.room.selected {
  background-color: rgba(0, 128, 0, 0.7);
}

.room-content {
  padding: 8px;
}

.room-name {
  font-size: 1.2em;
  font-weight: bold;
}

.room-category {
  font-size: 0.9em;
}

.empty {
  border: 1px dashed #555;
  background-color: rgba(0, 0, 0, 0.3);
}

.hover-preview {
  background-color: rgba(0, 255, 0, 0.3);
  z-index: 1;
}

.valid-placement .hover-preview {
  border: 2px solid #00ff00;
}

.invalid-placement .hover-preview {
  background-color: rgba(255, 0, 0, 0.3);
  border: 2px solid #ff0000;
}

.room-grid::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  border: 2px solid #00ff00;
  pointer-events: none;
  box-sizing: border-box;
}

.destroy-button {
  position: absolute;
  bottom: 4px;
  right: 4px;
  background-color: rgba(255, 0, 0, 0.7);
  color: white;
  border: none;
  border-radius: 50%;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background-color 0.3s;
}

.destroy-button:hover {
  background-color: rgba(255, 0, 0, 0.9);
}
</style>
