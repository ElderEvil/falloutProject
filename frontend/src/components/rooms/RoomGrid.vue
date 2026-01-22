<script setup lang="ts">
import { computed, defineAsyncComponent, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useRoomStore } from '@/stores/room'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useDwellerStore } from '@/stores/dweller'
import { useTrainingStore } from '@/stores/training'
import { useRoomInteractions } from '@/composables/useRoomInteractions'
import { useHoverPreview } from '@/composables/useHoverPreview'
import RoomDwellers from '@/modules/dwellers/components/RoomDwellers.vue'
import ComponentLoader from '@/core/components/common/ComponentLoader.vue'
import { Icon } from '@iconify/vue'
import type { Incident } from '@/models/incident'
import { IncidentType } from '@/models/incident'
import type { Room } from '@/models/room'

// Lazy load heavy modal
const RoomDetailModal = defineAsyncComponent({
  loader: () => import('@/components/rooms/RoomDetailModal.vue'),
  loadingComponent: ComponentLoader,
  delay: 200,
  timeout: 10000,
})

interface Props {
  incidents?: Incident[]
  highlightedRoomId?: string | null
}

const props = withDefaults(defineProps<Props>(), {
  incidents: () => [],
  highlightedRoomId: null
})

const emit = defineEmits<{
  incidentClicked: [incidentId: string]
}>()

const route = useRoute()
const roomStore = useRoomStore()
const authStore = useAuthStore()
const vaultStore = useVaultStore()
const dwellerStore = useDwellerStore()
const trainingStore = useTrainingStore()
const rooms = computed(() => Array.isArray(roomStore.rooms) ? roomStore.rooms : [])

// Power outage logic
const isPowerOutage = computed(() => {
  return (vaultStore.activeVault?.power ?? 1) <= 0
})

const isRoomAffectedByOutage = (room: Room) => {
  if (!isPowerOutage.value) return false
  // Power generators (STRENGTH) continue working
  return room.ability?.toLowerCase() !== 'strength'
}

const { selectedRoomId, toggleRoomSelection, destroyRoom } = useRoomInteractions()
const { hoverPosition, handleHover, clearHover, previewCells, isValidPlacement } = useHoverPreview()

// Room detail modal state
const showDetailModal = ref(false)
const selectedRoomForDetail = ref<Room | null>(null)

// Grid configuration
const GRID_COLS = 8  // Expanded from 4 to accommodate more rooms
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
        speedup_multiplier: selectedRoom.speedup_multiplier || 1,
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

    // Find the target room to check if it's a training room
    const targetRoom = rooms.value.find(r => r.id === roomId)

    // Assign dweller to room
    await dwellerStore.assignDwellerToRoom(dwellerId, roomId, authStore.token as string)

    // If it's a training room, start a training session
    if (targetRoom?.category?.toLowerCase() === 'training') {
      await trainingStore.startTraining(dwellerId, roomId, authStore.token as string)
    }

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

// Helper to check if room can be upgraded
const canUpgrade = (room: any) => {
  const maxTier = room.t2_upgrade_cost && room.t3_upgrade_cost ? 3 : room.t2_upgrade_cost ? 2 : 1
  return room.tier < maxTier
}

// Helper to get upgrade cost
const getUpgradeCost = (room: any) => {
  if (room.tier === 1 && room.t2_upgrade_cost) return room.t2_upgrade_cost
  if (room.tier === 2 && room.t3_upgrade_cost) return room.t3_upgrade_cost
  return 0
}

// Incident helpers
const roomHasIncident = (roomId: string) => {
  return props.incidents.some(incident => incident.room_id === roomId)
}

const getRoomIncident = (roomId: string) => {
  return props.incidents.find(incident => incident.room_id === roomId)
}

const getIncidentIcon = (type: IncidentType) => {
  switch (type) {
    case IncidentType.RAIDER_ATTACK:
      return 'mdi:skull'
    case IncidentType.RADROACH_INFESTATION:
      return 'mdi:bug'
    case IncidentType.FIRE:
      return 'mdi:fire'
    case IncidentType.MOLE_RAT_ATTACK:
      return 'mdi:paw'
    case IncidentType.DEATHCLAW_ATTACK:
      return 'mdi:claw-mark'
    case IncidentType.RADIATION_LEAK:
      return 'mdi:radioactive'
    case IncidentType.ELECTRICAL_FAILURE:
      return 'mdi:lightning-bolt'
    case IncidentType.WATER_CONTAMINATION:
      return 'mdi:water-alert'
    default:
      return 'mdi:alert-octagon'
  }
}

const handleIncidentClick = (roomId: string, event: MouseEvent) => {
  event.stopPropagation()
  const incident = getRoomIncident(roomId)
  if (incident) {
    emit('incidentClicked', incident.id)
  }
}

// Upgrade room handler
const handleUpgradeRoom = async (roomId: string, event: MouseEvent) => {
  event.stopPropagation()

  const vaultId = route.params.id as string
  if (!vaultId) {
    assignmentError.value = 'No vault ID available'
    setTimeout(() => { assignmentError.value = null }, 3000)
    return
  }

  try {
    await roomStore.upgradeRoom(roomId, authStore.token as string, vaultId)
    assignmentSuccess.value = 'Room upgraded successfully!'
    setTimeout(() => {
      assignmentSuccess.value = null
    }, 3000)
  } catch (error) {
    console.error('Failed to upgrade room:', error)
    assignmentError.value = error instanceof Error ? error.message : 'Failed to upgrade room'
    setTimeout(() => {
      assignmentError.value = null
    }, 3000)
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
    <!-- Success/Error notifications -->
    <div v-if="assignmentSuccess" class="notification notification-success">
      <Icon icon="mdi:check-circle" class="h-5 w-5" />
      {{ assignmentSuccess }}
    </div>
    <div v-if="assignmentError" class="notification notification-error">
      <Icon icon="mdi:alert-circle" class="h-5 w-5" />
      {{ assignmentError }}
    </div>

    <!-- Room Detail Modal -->
    <RoomDetailModal
      :room="selectedRoomForDetail"
      v-model="showDetailModal"
      @close="closeDetailModal"
      @room-updated="handleRoomUpdated"
    />

    <div class="room-grid" :class="{ 'critical-power': isPowerOutage }">
      <!-- Render built rooms -->
      <div
        v-for="room in rooms"
        :key="room.id"
        :style="{
          gridRow: (room.coordinate_y ?? 0) + 1,
          gridColumn: `${(room.coordinate_x ?? 0) + 1} / span ${room.size === 1 ? 1 : Math.ceil((room.size || room.size_min) / 3)}`
        }"
        class="room built-room"
        :class="{
          selected: selectedRoomId === room.id,
          'drag-over': draggingOverRoomId === room.id,
          'has-incident': roomHasIncident(room.id),
          'highlighted': highlightedRoomId === room.id,
          'power-outage': isRoomAffectedByOutage(room)
        }"
        @click="handleRoomClick(room, $event)"
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
          <div v-if="selectedRoomId === room.id" class="room-actions">
            <button
              v-if="canUpgrade(room)"
              @click="handleUpgradeRoom(room.id, $event)"
              class="upgrade-button"
              :title="`Upgrade to Tier ${room.tier + 1} (${getUpgradeCost(room)} caps)`"
            >
              <Icon icon="mdi:arrow-up-circle" class="h-5 w-5" />
              <span class="upgrade-cost">{{ getUpgradeCost(room) }}</span>
            </button>
            <button
              @click="destroyRoom(room.id, $event)"
              class="destroy-button"
              title="Destroy Room"
            >
              <Icon icon="mdi:delete" class="h-5 w-5" />
            </button>
          </div>

          <!-- Display dwellers in room -->
          <RoomDwellers :roomId="room.id" />

          <!-- Incident overlay -->
          <div v-if="roomHasIncident(room.id)" class="incident-overlay" @click="handleIncidentClick(room.id, $event)">
            <Icon :icon="getIncidentIcon(getRoomIncident(room.id)!.type)" class="incident-icon" />
            <div class="incident-label">ALERT</div>
          </div>
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

      <!-- Locked rows indicator (16-25) -->
      <div
        v-for="y in 9"
        :key="`locked-${y}`"
        class="locked-row"
        :style="{
          gridRow: GRID_ROWS + y,
          gridColumn: '1 / -1'
        }"
      >
        <Icon icon="mdi:lock" class="locked-icon" />
        <span class="locked-text">Locked Area - Future Expansion (Row {{ GRID_ROWS + y - 1 }})</span>
      </div>
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
  border: 2px solid var(--color-theme-primary);
  color: var(--color-theme-primary);
}

.notification-error {
  background: rgba(128, 0, 0, 0.9);
  border: 2px solid #ff0000;
  color: #ff0000;
}

.room-grid {
  display: grid;
  grid-template-columns: repeat(8, minmax(140px, 1fr)); /* 8 columns with larger min width */
  grid-template-rows: repeat(16, 140px) repeat(9, 80px);  /* 16 active rows (larger) + 9 locked rows */
  gap: 10px;
  width: 100%;
  max-width: 100%;
  overflow-x: auto;
}

.locked-row {
  background: linear-gradient(
    135deg,
    rgba(60, 60, 60, 0.3),
    rgba(40, 40, 40, 0.3)
  );
  border: 2px dashed #444;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  color: #666;
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
  color: #555;
}

.locked-text {
  font-weight: 500;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  font-size: 0.75rem;
}

.room {
  position: relative;
  background-color: #333;
  border: 1px solid #555;
  cursor: pointer;
  transition: all 0.2s;
  min-height: 140px;
  height: 100%;
  display: flex;
  flex-direction: column;
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
  0%, 100% {
    box-shadow: 0 0 20px var(--color-theme-primary);
  }
  50% {
    box-shadow: 0 0 40px var(--color-theme-primary);
  }
}

.room-content {
  padding: 10px;
  text-align: center;
  position: relative;
}

.room-name {
  font-size: 0.95em; /* Reduced from 1.2em */
  margin-bottom: 5px;
  color: var(--color-theme-primary);
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
  color: var(--color-theme-primary);
  font-size: 0.875rem;
  font-weight: bold;
  pointer-events: none;
  z-index: 10;
}

.room-actions {
  position: absolute;
  top: 5px;
  right: 5px;
  display: flex;
  gap: 8px;
  align-items: center;
  z-index: 5;
}

.upgrade-button {
  background: none;
  border: 1px solid #fbbf24;
  border-radius: 4px;
  cursor: pointer;
  color: #fbbf24;
  padding: 4px 8px;
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 0.75rem;
  transition: all 0.2s;
}

.upgrade-button:hover {
  background: rgba(251, 191, 36, 0.1);
  box-shadow: 0 0 8px rgba(251, 191, 36, 0.5);
}

.upgrade-cost {
  font-weight: bold;
}

/* Incident styles */
.room.has-incident {
  border-color: #ff3333;
  box-shadow: 0 0 15px rgba(255, 51, 51, 0.6);
  animation: incident-pulse 2s ease-in-out infinite;
}

@keyframes incident-pulse {
  0%,
  100% {
    border-color: #ff3333;
    box-shadow: 0 0 15px rgba(255, 51, 51, 0.6);
  }
  50% {
    border-color: #ff5555;
    box-shadow: 0 0 30px rgba(255, 51, 51, 0.9);
  }
}

.incident-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255, 0, 0, 0.15);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  cursor: pointer;
  z-index: 20;
  transition: background 0.3s ease;
}

.incident-overlay:hover {
  background: rgba(255, 0, 0, 0.25);
}

.incident-icon {
  width: 48px;
  height: 48px;
  color: #ff3333;
  filter: drop-shadow(0 0 8px rgba(255, 51, 51, 0.8));
  animation: incident-shake 0.5s ease-in-out infinite;
}

@keyframes incident-shake {
  0%,
  100% {
    transform: translate(0, 0) rotate(0deg);
  }
  25% {
    transform: translate(-2px, 0) rotate(-2deg);
  }
  75% {
    transform: translate(2px, 0) rotate(2deg);
  }
}

.incident-label {
  font-family: 'Courier New', monospace;
  font-size: 0.875rem;
  font-weight: bold;
  color: #ff3333;
  letter-spacing: 0.1em;
  text-shadow: 0 0 8px rgba(255, 51, 51, 0.8);
}

.destroy-button {
  background: none;
  border: none;
  cursor: pointer;
  color: #ff0000;
  padding: 4px;
  transition: all 0.2s;
}

.destroy-button:hover {
  color: #ff4444;
  transform: scale(1.1);
}

.empty {
  border: 1px dashed #555;
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
  border: 2px solid #ff0000;
}

.room.power-outage {
  filter: brightness(0.3) grayscale(0.8);
  border-color: #330000;
  pointer-events: none; /* Disable interaction with powerless rooms */
}

.room.power-outage .room-name,
.room.power-outage .room-category {
  color: #666;
}

.critical-power {
  animation: critical-pulse 2s infinite;
  border: 2px solid rgba(255, 0, 0, 0.5);
}

@keyframes critical-pulse {
  0% { box-shadow: 0 0 10px rgba(255, 0, 0, 0.2) inset; }
  50% { box-shadow: 0 0 50px rgba(255, 0, 0, 0.5) inset; }
  100% { box-shadow: 0 0 10px rgba(255, 0, 0, 0.2) inset; }
}
</style>
