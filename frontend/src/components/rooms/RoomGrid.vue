<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoomStore } from '@/stores/room'
import { useAuthStore } from '@/stores/auth'
import { useDwellerStore } from '@/stores/dweller'
import { useRoomInteractions } from '@/composables/useRoomInteractions'
import { useHoverPreview } from '@/composables/useHoverPreview'
import RoomDwellers from '@/components/dwellers/RoomDwellers.vue'
import { Icon } from '@iconify/vue'

const roomStore = useRoomStore()
const authStore = useAuthStore()
const dwellerStore = useDwellerStore()
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

// Drag and drop for dweller assignment
const draggingOverRoomId = ref<string | null>(null)
const assignmentError = ref<string | null>(null)
const assignmentSuccess = ref<string | null>(null)

const handleDragOver = (event: DragEvent, roomId: string) => {
  event.preventDefault()
  event.dataTransfer!.dropEffect = 'move'
  draggingOverRoomId.value = roomId
}

const handleDragLeave = () => {
  draggingOverRoomId.value = null
}

const handleDrop = async (event: DragEvent, roomId: string) => {
  event.preventDefault()
  draggingOverRoomId.value = null
  assignmentError.value = null
  assignmentSuccess.value = null

  try {
    const data = JSON.parse(event.dataTransfer!.getData('application/json'))
    const { dwellerId, firstName, lastName, currentRoomId } = data

    // Check if moving to same room
    if (currentRoomId === roomId) {
      return
    }

    await dwellerStore.assignDwellerToRoom(dwellerId, roomId, authStore.token as string)

    const action = currentRoomId ? 'moved' : 'assigned'
    assignmentSuccess.value = `${firstName} ${lastName} ${action} successfully!`
    setTimeout(() => {
      assignmentSuccess.value = null
    }, 3000)
  } catch (error) {
    console.error('Failed to assign dweller:', error)
    assignmentError.value = 'Failed to assign dweller to room'
    setTimeout(() => {
      assignmentError.value = null
    }, 3000)
  }
}
</script>

<template>
  <div class="room-grid-container">
    <!-- Success/Error notifications -->
    <div v-if="assignmentSuccess" class="notification notification-success">
      <Icon icon="mdi:check-circle" class="h-5 w-5" />
      {{ assignmentSuccess }}
    </div>
    <div v-if="assignmentError" class="notification notification-error">
      <Icon icon="mdi:alert-circle" class="h-5 w-5" />
      {{ assignmentError }}
    </div>

    <div class="room-grid">
      <div
        v-for="room in rooms"
        :key="room.id"
        :style="{
          gridRow: room.coordinate_y + 1,
          gridColumn: `${room.coordinate_x + 1} / span ${Math.ceil(room.size / 3)}`
        }"
        class="room"
        :class="{
          selected: selectedRoomId === room.id,
          'drag-over': draggingOverRoomId === room.id
        }"
        @click="toggleRoomSelection(room.id)"
        @dragover="handleDragOver($event, room.id)"
        @dragleave="handleDragLeave"
        @drop="handleDrop($event, room.id)"
      >
        <div class="room-content">
          <h3 class="room-number">{{ room.number }}</h3>
          <p class="room-category">{{ room.category }}</p>
          <div v-if="draggingOverRoomId === room.id" class="drop-indicator">
            <Icon icon="mdi:account-plus" class="h-6 w-6" />
            <span>Drop to assign</span>
          </div>
          <button
            v-if="selectedRoomId === room.id"
            @click="destroyRoom(room.id, $event)"
            class="destroy-button"
            title="Destroy Room"
          >
            <Icon icon="mdi:delete" class="h-5 w-5" />
          </button>

          <!-- Display dwellers in room -->
          <RoomDwellers :roomId="room.id" />
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
  </div>
</template>

<style scoped>
.room-grid-container {
  position: relative;
}

.notification {
  position: fixed;
  top: 20px;
  right: 20px;
  padding: 1rem;
  border-radius: 8px;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-family: 'Courier New', monospace;
  z-index: 1000;
  animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

.notification-success {
  background: rgba(0, 128, 0, 0.9);
  border: 2px solid #00ff00;
  color: #00ff00;
}

.notification-error {
  background: rgba(128, 0, 0, 0.9);
  border: 2px solid #ff0000;
  color: #ff0000;
}

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
  transition: all 0.2s;
}

.room.selected {
  border-color: #00ff00;
  transform: scale(1.05);
}

.room.drag-over {
  border-color: #00ff00;
  border-width: 3px;
  background-color: rgba(0, 255, 0, 0.1);
  box-shadow: 0 0 20px rgba(0, 255, 0, 0.4);
}

.room-content {
  padding: 10px;
  text-align: center;
  position: relative;
}

.room-number {
  font-size: 1.2em;
  margin-bottom: 5px;
}

.room-category {
  font-size: 0.9em;
  color: #aaa;
}

.drop-indicator {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
  color: #00ff00;
  font-size: 0.875rem;
  font-weight: bold;
  pointer-events: none;
  z-index: 10;
}

.destroy-button {
  position: absolute;
  top: 5px;
  right: 5px;
  background: none;
  border: none;
  cursor: pointer;
  color: #ff0000;
  z-index: 5;
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
