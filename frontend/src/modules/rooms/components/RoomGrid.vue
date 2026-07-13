<script setup lang="ts">
import { computed, defineAsyncComponent, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useRoomStore } from '../stores/room'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useTrainingStore } from '@/modules/progression/stores/training'
import { useRoomInteractions } from '../composables/useRoomInteractions'
import { useHoverPreview } from '../composables/useHoverPreview'
import { useRoomRendering } from '../composables/useRoomRendering'
import { useToast } from '@/core/composables/useToast'
import ComponentLoader from '@/core/components/common/ComponentLoader.vue'
import { Icon } from '@iconify/vue'
import type { Incident } from '@/modules/combat/models/incident'
import type { Room } from '../models/room'
import RoomGridCell from './RoomGridCell.vue'

// Lazy load heavy modal
const RoomDetailModal = defineAsyncComponent({
  loader: () => import('./RoomDetailModal.vue'),
  loadingComponent: ComponentLoader,
  delay: 200,
  timeout: 10000,
})

interface Props {
  incidents?: Incident[]
  highlightedRoomId?: string | null
}

const { incidents, highlightedRoomId } = defineProps<Props>()

const emit = defineEmits<{
  incidentClicked: [incidentId: string]
}>()

const route = useRoute()
const roomStore = useRoomStore()
const authStore = useAuthStore()
const vaultStore = useVaultStore()
const dwellerStore = useDwellerStore()
const trainingStore = useTrainingStore()
const toast = useToast()
const rooms = computed(() => (Array.isArray(roomStore.rooms) ? roomStore.rooms : []))

// Power outage logic
const isPowerOutage = computed(() => {
  return (vaultStore.activeVault?.power ?? 1) <= 0
})

const { selectedRoomId, toggleRoomSelection, destroyRoom } = useRoomInteractions()
const { hoverPosition, handleHover, clearHover, previewCells, isValidPlacement } = useHoverPreview()
const { showRoomImages } = useRoomRendering()

// Room detail modal state
const showDetailModal = ref(false)
const selectedRoomForDetail = ref<Room | null>(null)

// Grid configuration
const GRID_COLS = 8 // Expanded from 4 to accommodate more rooms
const GRID_ROWS = 16 // Expanded from 8 (rows 16-25 locked for future expansion)

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
    toast.error('No vault ID available')
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
        size_min: selectedRoom.size_min,
        size_max: selectedRoom.size_max,
        size: selectedRoom.size_min, // Use size_min as initial size
        tier: selectedRoom.tier || 1,
        coordinate_x: placementX,
        coordinate_y: y,
        image_url: selectedRoom.image_url,
        speedup_multiplier: selectedRoom.speedup_multiplier || 1,
        vault_id: vaultId,
      },
      authStore.token as string,
      vaultId
    )
    roomStore.deselectRoom()
    toast.success(`${selectedRoom.name} built successfully!`)
  } catch (error) {
    toast.error(error instanceof Error ? error.message : 'Failed to build room')
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
  return rooms.value.some((r) => {
    const roomX = r.coordinate_x ?? 0
    const roomY = r.coordinate_y ?? 0
    const roomWidth = Math.ceil((r.size || r.size_min) / 3)
    return roomY === y && roomX <= x && roomX + roomWidth > x
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

  try {
    const data = JSON.parse(event.dataTransfer!.getData('application/json'))
    const { dwellerId, firstName, lastName, currentRoomId } = data

    // Check if moving to same room
    if (currentRoomId === roomId) {
      return
    }

    // Find the target room
    const targetRoom = rooms.value.find((r) => r.id === roomId)

    // Check room capacity
    if (targetRoom) {
      const roomSize = targetRoom.size || targetRoom.size_min || 3
      const cellsOccupied = Math.ceil(roomSize / 3)
      const capacity = cellsOccupied * 2
      const currentDwellers = dwellerStore.dwellers.filter((d) => d.room_id === roomId).length

      // Prevent assignment if room is full (unless moving from same room)
      if (currentDwellers >= capacity && currentRoomId !== roomId) {
        toast.warning(`${targetRoom.name} is full (${currentDwellers}/${capacity})`)
        return
      }
    }

    // Assign dweller to room
    await dwellerStore.assignDwellerToRoom(dwellerId, roomId, authStore.token as string)

    // If it's a training room, start a training session
    if (targetRoom?.category?.toLowerCase() === 'training') {
      await trainingStore.startTraining(dwellerId, roomId, authStore.token as string)
    }

    const action = currentRoomId ? 'moved' : 'assigned'
    toast.success(`${firstName} ${lastName} ${action} successfully!`)
  } catch (error) {
    toast.error('Failed to assign dweller to room')
  }
}

// Incident helper
const getRoomIncident = (roomId: string) => {
  return (incidents ?? []).find((incident) => incident.room_id === roomId)
}

const handleIncidentClick = (incidentId: string) => {
  emit('incidentClicked', incidentId)
}

// Upgrade room handler
const handleUpgradeRoom = async (roomId: string, event: MouseEvent) => {
  event.stopPropagation()

  const vaultId = route.params.id as string
  if (!vaultId) {
    toast.error('No vault ID available')
    return
  }

  try {
    await roomStore.upgradeRoom(roomId, authStore.token as string, vaultId)
    toast.success('Room upgraded successfully!')
  } catch (error) {
    toast.error(error instanceof Error ? error.message : 'Failed to upgrade room')
  }
}

// Handle room click to open detail modal
const handleRoomClick = (room: Room, event: MouseEvent) => {
  // Don't open detail modal if clicking on action buttons or incident overlay
  const target = event.target as HTMLElement
  if (
    target.closest('.room-actions') ||
    target.closest('.incident-overlay') ||
    target.closest('button')
  ) {
    return
  }

  selectedRoomForDetail.value = room
  showDetailModal.value = true
}

// Handle room updated from detail modal
const handleRoomUpdated = async () => {
  const vaultId = route.params.id as string
  if (vaultId && authStore.token) {
    await roomStore.fetchRooms(vaultId, authStore.token)
    await dwellerStore.fetchDwellersByVault(vaultId, authStore.token)
  }
}

// Close detail modal
const closeDetailModal = () => {
  showDetailModal.value = false
  selectedRoomForDetail.value = null
}
</script>

<template>
  <div class="room-grid-container">
    <!-- Room Detail Modal -->
    <RoomDetailModal
      :room="selectedRoomForDetail"
      v-model="showDetailModal"
      @close="closeDetailModal"
      @room-updated="handleRoomUpdated"
    />

    <div class="room-grid" :class="{ 'critical-power': isPowerOutage }">
      <RoomGridCell
        v-for="room in rooms"
        :key="room.id"
        :room="room"
        :show-room-images="showRoomImages"
        :is-power-outage="isPowerOutage"
        :incident="getRoomIncident(room.id)"
        :selected="selectedRoomId === room.id"
        :is-dragging-over="draggingOverRoomId === room.id"
        :highlighted="highlightedRoomId != null && highlightedRoomId === room.id"
        @click="handleRoomClick"
        @upgrade="handleUpgradeRoom"
        @destroy="destroyRoom"
        @incident-click="handleIncidentClick"
        @dragover="handleDragOver"
        @dragleave="handleDragLeave"
        @drop="handleDrop"
      />

      <!-- Render empty cells -->
      <div
        v-for="cell in gridCells"
        :key="cell.key"
        :style="{
          gridRow: cell.y + 1,
          gridColumn: cell.x + 1,
        }"
        class="room empty"
        :class="{
          'hover-preview': previewCells.some(
            (previewCell) => previewCell.x === cell.x && previewCell.y === cell.y
          ),
          'valid-placement':
            isValidPlacement &&
            previewCells.some(
              (previewCell) => previewCell.x === cell.x && previewCell.y === cell.y
            ),
          'invalid-placement':
            !isValidPlacement &&
            hoverPosition &&
            previewCells.some(
              (previewCell) => previewCell.x === cell.x && previewCell.y === cell.y
            ),
        }"
        @mouseenter="handleHover(cell.x, cell.y)"
        @mouseleave="clearHover"
        role="button"
        tabindex="0"
        @click="handleEmptyCellClick(cell.x, cell.y)"
        @keydown.enter.prevent="handleEmptyCellClick(cell.x, cell.y)"
        @keydown.space.prevent="handleEmptyCellClick(cell.x, cell.y)"
      ></div>

      <!-- Locked rows indicator (16-25) -->
      <div
        v-for="y in 9"
        :key="`locked-${y}`"
        class="locked-row"
        :style="{
          gridRow: GRID_ROWS + y,
          gridColumn: '1 / -1',
        }"
      >
        <Icon icon="mdi:lock" class="locked-icon" />
        <span class="locked-text"
          >Locked Area - Future Expansion (Row {{ GRID_ROWS + y - 1 }})</span
        >
      </div>
    </div>
  </div>
</template>

<style scoped>
.room-grid-container {
  position: relative;
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
  background: rgba(0, 0, 0, 0.95);
  border: 2px solid var(--color-theme-primary);
  color: var(--color-theme-primary);
  box-shadow: 0 0 20px var(--color-theme-glow);
}

.notification-error {
  background: rgba(0, 0, 0, 0.95);
  border: 2px solid var(--color-danger);
  color: var(--color-danger);
  box-shadow: 0 0 20px rgba(255, 0, 0, 0.3);
}

.room-grid {
  display: grid;
  grid-template-columns: repeat(8, minmax(140px, 1fr)); /* 8 columns with larger min width */
  grid-template-rows: repeat(16, 140px) repeat(9, 80px); /* 16 active rows (larger) + 9 locked rows */
  gap: 10px;
  width: 100%;
  max-width: 100%;
  overflow-x: auto;
}

.locked-row {
  background: linear-gradient(135deg, rgba(60, 60, 60, 0.3), rgba(40, 40, 40, 0.3));
  border: 2px dashed var(--color-gray-700);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  color: var(--color-gray-500);
  font-family: 'Courier New', monospace;
  font-size: 0.85rem;
  pointer-events: none;
  position: relative;
  overflow: hidden;
}

.locked-row::before {
  content: '';
  position: absolute;
  inset: 0;
  background: repeating-linear-gradient(
    45deg,
    transparent,
    transparent 10px,
    rgba(255, 255, 255, 0.02) 10px,
    rgba(255, 255, 255, 0.02) 20px
  );
}

.locked-icon {
  width: 1.5rem;
  height: 1.5rem;
  color: var(--color-gray-600);
}
.locked-text {
  font-weight: 500;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  font-size: 0.75rem;
}

.room {
  position: relative;
  background-color: var(--color-gray-700);
  border: 1px solid var(--color-gray-600);
  cursor: pointer;
  transition: all 0.2s;
  min-height: 140px;
  height: 100%;
  display: flex;
  flex-direction: column;
  user-select: none;
  -webkit-user-drag: none;
}

.room.selected {
  border-color: var(--color-theme-primary);
  transform: scale(1.05);
}

.room.drag-over {
  border-color: var(--color-theme-primary);
  border-width: 3px;
  background-color: var(--color-theme-glow);
  box-shadow: 0 0 20px var(--color-theme-glow);
}

.room.highlighted {
  border-color: var(--color-theme-primary);
  border-width: 3px;
  box-shadow: 0 0 30px var(--color-theme-primary);
  animation: highlight-pulse 1s ease-in-out 3;
}

@keyframes highlight-pulse {
  0%,
  100% {
    box-shadow: 0 0 20px var(--color-theme-primary);
  }
  50% {
    box-shadow: 0 0 40px var(--color-theme-primary);
  }
}

/* Incident styles */
.room.has-incident {
  border-color: var(--color-danger);
  box-shadow: 0 0 15px rgba(255, 51, 51, 0.6);
  animation: incident-pulse 2s ease-in-out infinite;
}

@keyframes incident-pulse {
  0%,
  100% {
    border-color: var(--color-danger);
    box-shadow: 0 0 15px rgba(255, 51, 51, 0.6);
  }
  50% {
    border-color: var(--color-danger);
    box-shadow: 0 0 30px rgba(255, 51, 51, 0.9);
  }
}

.empty {
  border: 1px dashed var(--color-gray-600);
  background-color: rgba(0, 0, 0, 0.3);
  aspect-ratio: 2 / 1;
  min-height: 80px;
}

.hover-preview {
  background-color: var(--color-theme-glow);
  z-index: 1;
}

.valid-placement .hover-preview {
  background-color: transparent;
  background-image: linear-gradient(
    45deg,
    var(--color-theme-glow) 25%,
    transparent 25%,
    transparent 50%,
    var(--color-theme-glow) 50%,
    var(--color-theme-glow) 75%,
    transparent 75%,
    transparent
  );
  background-size: 20px 20px;
  border: 2px solid var(--color-theme-primary);
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
  border: 2px solid var(--color-danger);
}

.room.power-outage {
  filter: brightness(0.3) grayscale(0.8);
  border-color: var(--color-surface-dark);
  pointer-events: none; /* Disable interaction with powerless rooms */
}

.critical-power {
  animation: critical-pulse 2s infinite;
  border: 2px solid rgba(255, 0, 0, 0.5);
}

@keyframes critical-pulse {
  0% {
    box-shadow: 0 0 10px rgba(255, 0, 0, 0.2) inset;
  }
  50% {
    box-shadow: 0 0 50px rgba(255, 0, 0, 0.5) inset;
  }
  100% {
    box-shadow: 0 0 10px rgba(255, 0, 0, 0.2) inset;
  }
}
</style>
