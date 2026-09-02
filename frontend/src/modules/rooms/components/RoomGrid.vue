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
import { useRoomRendering } from '@/core/composables/useRoomRendering'
import { useToast } from '@/core/composables/useToast'
import ComponentLoader from '@/core/components/common/ComponentLoader.vue'
import { Icon } from '@iconify/vue'
import type { Incident } from '@/modules/combat/models/incident'
import type { OverseerBriefingData } from '@/modules/vault/models/overseerBriefing'
import type { Room } from '../models/room'
import { getTrainingRoomCapacity, isLevelBuildable } from '@/modules/rooms/utils/room'
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
  overseerBriefing?: OverseerBriefingData
  overseerAttentionCount?: number
}

const { incidents, highlightedRoomId, overseerBriefing, overseerAttentionCount } = defineProps<Props>()

const emit = defineEmits<{
  incidentClicked: [incidentId: string]
  reviewIncidents: []
}>()

const route = useRoute()
const roomStore = useRoomStore()
const authStore = useAuthStore()
const vaultStore = useVaultStore()
const { filter: dwellerStore, management: dwellerManagementStore } = useDwellerStore()
const trainingStore = useTrainingStore()
const toast = useToast()
const rooms = computed(() => (Array.isArray(roomStore.rooms) ? roomStore.rooms : []))
const vaultId = computed(() => (route?.params.id as string) ?? '')

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
    await roomStore.buildRoom(selectedRoom.name, placementX, y, authStore.token as string, vaultId)
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

// Generate grid cells for all levels
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

// A level without an elevator is locked until one is built on it.
// Row 0 is always buildable because the vault door anchors it.
const isLevelLocked = (y: number) => !isLevelBuildable(rooms.value, y)

// Elevators can still be placed on locked levels (stacked below an existing
// shaft) because building one is exactly what unlocks the level.
const isPlacingElevator = computed(
  () => roomStore.selectedRoom?.name.toLowerCase() === 'elevator'
)
const canInteractWithLevel = (y: number) => !isLevelLocked(y) || isPlacingElevator.value

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

    // Check room capacity. Youth apprentices sit outside worker capacity
    // (backend policy: one per production room) — gate adults on staffed
    // slots only; apprentices never count toward them.
    if (targetRoom && dwellerStore.dwellers.find((d) => d.id === dwellerId)?.is_adult !== false) {
      const capacity = getTrainingRoomCapacity(targetRoom)
      const staffedDwellers = dwellerStore.dwellers.filter(
        (d) => d.room_id === roomId && !d.apprentice_stat
      ).length
      if (staffedDwellers >= capacity) {
        toast.warning(`${targetRoom.name} is full (${staffedDwellers}/${capacity})`)
        return
      }
    }

    // Assign dweller to room
    await dwellerManagementStore.assignDwellerToRoom(dwellerId, roomId, authStore.token as string)

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
const handleRoomClick = (room: Room, event: MouseEvent | KeyboardEvent) => {
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
      :overseer-briefing="overseerBriefing"
      :vault-id="vaultId"
      v-model="showDetailModal"
      @close="closeDetailModal"
      @room-updated="handleRoomUpdated"
      @review-incidents="emit('reviewIncidents')"
    />

    <div class="room-grid" :class="{ 'critical-power': isPowerOutage }">
      <RoomGridCell
        v-for="room in rooms"
        :key="room.id"
        :room="room"
        :show-room-images="showRoomImages"
        :is-power-outage="isPowerOutage"
        :incident="getRoomIncident(room.id)"
        :overseer-attention-count="overseerAttentionCount"
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
          'level-locked': isLevelLocked(cell.y) && !isPlacingElevator,
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
        @mouseenter="canInteractWithLevel(cell.y) && handleHover(cell.x, cell.y)"
        @mouseleave="clearHover"
        :role="roomStore.isPlacingRoom && canInteractWithLevel(cell.y) ? 'button' : undefined"
        :tabindex="roomStore.isPlacingRoom && canInteractWithLevel(cell.y) ? 0 : undefined"
        :aria-label="
          isLevelLocked(cell.y) && !isPlacingElevator
            ? `Level ${cell.y + 1} is locked`
            : roomStore.isPlacingRoom
              ? `Build room at row ${cell.y + 1}, column ${cell.x + 1}`
              : `Empty room cell at row ${cell.y + 1}, column ${cell.x + 1}`
        "
        @click="canInteractWithLevel(cell.y) && handleEmptyCellClick(cell.x, cell.y)"
        @keydown.enter.prevent="canInteractWithLevel(cell.y) && handleEmptyCellClick(cell.x, cell.y)"
        @keydown.space.prevent="canInteractWithLevel(cell.y) && handleEmptyCellClick(cell.x, cell.y)"
      >
        <span v-if="isLevelLocked(cell.y) && !isPlacingElevator" class="level-lock-indicator">
          <Icon icon="mdi:lock" />
        </span>
      </div>

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

<style src="./RoomGrid.css" scoped></style>
