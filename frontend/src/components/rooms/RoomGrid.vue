<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useRoomStore } from '@/stores/room'
import { useAuthStore } from '@/stores/auth'
import { useDwellerStore } from '@/stores/dweller'
import { useRoomInteractions } from '@/composables/useRoomInteractions'
import { useHoverPreview } from '@/composables/useHoverPreview'
import RoomDwellers from '@/components/dwellers/RoomDwellers.vue'
import { Icon } from '@iconify/vue'

const route = useRoute()
const roomStore = useRoomStore()
const authStore = useAuthStore()
const dwellerStore = useDwellerStore()
const rooms = computed(() => Array.isArray(roomStore.rooms) ? roomStore.rooms : [])

const { selectedRoomId, toggleRoomSelection, destroyRoom } = useRoomInteractions()
const { hoverPosition, handleHover, clearHover, previewCells, isValidPlacement } = useHoverPreview()

// Grid configuration
const GRID_COLS = 8
const GRID_ROWS = 25

const placeRoom = async (x: number, y: number) => {
  if (!roomStore.selectedRoom || !roomStore.isPlacingRoom) return

  const selectedRoom = roomStore.selectedRoom
  const roomSizeMin = selectedRoom.size_min
  const cellsCount = Math.ceil(roomSizeMin / 3)

  // Calculate placement X based on room size
  const placementX = cellsCount === 1 ? x : x - Math.floor(cellsCount / 2)

  // Get vault ID from route
  const vaultId = route.params.id as string
  if (!vaultId) {
    console.error('No vault ID available')
    assignmentError.value = 'No vault ID available'
    setTimeout(() => { assignmentError.value = null }, 3000)
    return
  }

  try {
    await roomStore.buildRoom(
      {
        name: selectedRoom.name,
        category: selectedRoom.category,
        ability: selectedRoom.ability,
        population_required: selectedRoom.population_required,
        base_cost: selectedRoom.base_cost,
        incremental_cost: selectedRoom.incremental_cost,
        t2_upgrade_cost: selectedRoom.t2_upgrade_cost,
        t3_upgrade_cost: selectedRoom.t3_upgrade_cost,
        capacity: selectedRoom.capacity,
        output: selectedRoom.output,
        size_min: selectedRoom.size_min,
        size_max: selectedRoom.size_max,
        size: selectedRoom.size_min, // Use size_min as initial size
        tier: selectedRoom.tier || 1,
        coordinate_x: placementX,
        coordinate_y: y,
        image_url: selectedRoom.image_url,
        vault_id: vaultId
      },
      authStore.token as string,
      vaultId
    )
    roomStore.deselectRoom()
    assignmentSuccess.value = `${selectedRoom.name} built successfully!`
    setTimeout(() => {
      assignmentSuccess.value = null
    }, 3000)
  } catch (error) {
    console.error('Failed to build room:', error)
    assignmentError.value = error instanceof Error ? error.message : 'Failed to build room'
    setTimeout(() => {
      assignmentError.value = null
    }, 3000)
  }
}

// Handle click on empty cell
const handleEmptyCellClick = (x: number, y: number) => {
  if (roomStore.isPlacingRoom && isValidPlacement.value) {
    placeRoom(x, y)
  }
}

// Helper to check if a cell is occupied by a room
const isCellOccupied = (x: number, y: number) => {
  return rooms.value.some(r => {
    const roomX = r.coordinate_x ?? 0
    const roomY = r.coordinate_y ?? 0
    const roomWidth = Math.ceil((r.size || r.size_min) / 3)
    return roomY === y && roomX <= x && (roomX + roomWidth) > x
  })
}

// Generate grid cells
const gridCells = computed(() => {
  const cells: Array<{ x: number; y: number; key: string }> = []
  for (let y = 0; y < GRID_ROWS; y++) {
    for (let x = 0; x < GRID_COLS; x++) {
      if (!isCellOccupied(x, y)) {
        cells.push({ x, y, key: `${x}-${y}` })
      }
    }
  }
  return cells
})

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
      <!-- Render built rooms -->
      <div
        v-for="room in rooms"
        :key="room.id"
        :style="{
          gridRow: (room.coordinate_y ?? 0) + 1,
          gridColumn: `${(room.coordinate_x ?? 0) + 1} / span ${Math.ceil((room.size || room.size_min) / 3)}`
        }"
        class="room built-room"
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
          <h3 class="room-name">{{ room.name }}</h3>
          <p class="room-category">{{ room.category }}</p>
          <div v-if="room.tier" class="room-tier">Tier {{ room.tier }}</div>
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

      <!-- Render empty cells -->
      <div
        v-for="cell in gridCells"
        :key="cell.key"
        :style="{
          gridRow: cell.y + 1,
          gridColumn: cell.x + 1
        }"
        class="room empty"
        :class="{
          'hover-preview': previewCells.some(
            (previewCell) => previewCell.x === cell.x && previewCell.y === cell.y
          ),
          'valid-placement': isValidPlacement && previewCells.some(
            (previewCell) => previewCell.x === cell.x && previewCell.y === cell.y
          ),
          'invalid-placement': !isValidPlacement && hoverPosition && previewCells.some(
            (previewCell) => previewCell.x === cell.x && previewCell.y === cell.y
          )
        }"
        @mouseenter="handleHover(cell.x, cell.y)"
        @mouseleave="clearHover"
        @click="handleEmptyCellClick(cell.x, cell.y)"
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
  min-height: 80px;
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

.room-name {
  font-size: 0.95em; /* Reduced from 1.2em */
  margin-bottom: 5px;
  color: #00ff00;
  font-weight: 600; /* Slightly less bold but still readable */
}

.room-category {
  font-size: 0.75em; /* Reduced from 0.9em */
  color: #aaa;
  font-weight: 500;
}

.room-tier {
  font-size: 0.65em; /* Reduced from 0.75em */
  color: #fbbf24;
  margin-top: 2px;
  font-weight: 600;
}

.built-room {
  background: linear-gradient(135deg, rgba(50, 50, 50, 0.9), rgba(30, 30, 30, 0.9));
  z-index: 2;
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
  min-height: 80px;
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
