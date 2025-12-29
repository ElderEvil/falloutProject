<script setup lang="ts">
import { computed, ref } from 'vue'
import { useDwellerStore } from '@/stores/dweller'
import { useAuthStore } from '@/stores/auth'
import { Icon } from '@iconify/vue'
import type { DwellerShort } from '@/models/dweller'

const dwellerStore = useDwellerStore()
const authStore = useAuthStore()

// Filter dwellers without room assignment
const unassignedDwellers = computed(() => {
  return dwellerStore.dwellers.filter(dweller => !dweller.room_id)
})

const isDraggingOver = ref(false)
const unassignError = ref<string | null>(null)
const unassignSuccess = ref<string | null>(null)

const emit = defineEmits<{
  dragStart: [dweller: DwellerShort]
  dragEnd: []
}>()

const handleDragStart = (event: DragEvent, dweller: DwellerShort) => {
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('application/json', JSON.stringify({
      dwellerId: dweller.id,
      firstName: dweller.first_name,
      lastName: dweller.last_name
    }))
  }
  emit('dragStart', dweller)
}

const handleDragEnd = () => {
  emit('dragEnd')
}

const handleDropZoneDragOver = (event: DragEvent) => {
  event.preventDefault()
  event.dataTransfer!.dropEffect = 'move'
  isDraggingOver.value = true
}

const handleDropZoneDragLeave = () => {
  isDraggingOver.value = false
}

const handleDropZoneDrop = async (event: DragEvent) => {
  event.preventDefault()
  isDraggingOver.value = false
  unassignError.value = null
  unassignSuccess.value = null

  try {
    const data = JSON.parse(event.dataTransfer!.getData('application/json'))
    const { dwellerId, firstName, lastName, currentRoomId } = data

    // Only unassign if dweller is currently in a room
    if (!currentRoomId) {
      return
    }

    await dwellerStore.unassignDwellerFromRoom(dwellerId, authStore.token as string)

    unassignSuccess.value = `${firstName} ${lastName} unassigned from room`
    setTimeout(() => {
      unassignSuccess.value = null
    }, 3000)
  } catch (error) {
    console.error('Failed to unassign dweller:', error)
    unassignError.value = 'Failed to unassign dweller'
    setTimeout(() => {
      unassignError.value = null
    }, 3000)
  }
}

const getImageUrl = (imagePath: string | null) => {
  if (!imagePath) return null
  return imagePath.startsWith('http') ? imagePath : `http://${imagePath}`
}
</script>

<template>
  <div class="unassigned-dwellers-panel">
    <!-- Success/Error notifications -->
    <div v-if="unassignSuccess" class="notification notification-success">
      <Icon icon="mdi:check-circle" class="h-5 w-5" />
      {{ unassignSuccess }}
    </div>
    <div v-if="unassignError" class="notification notification-error">
      <Icon icon="mdi:alert-circle" class="h-5 w-5" />
      {{ unassignError }}
    </div>

    <div class="panel-header">
      <h3 class="panel-title">
        <Icon icon="mdi:account-multiple" class="inline h-5 w-5" />
        Unassigned Dwellers
        <span class="count-badge">{{ unassignedDwellers.length }}</span>
      </h3>
      <p class="panel-subtitle">Drag dwellers here to unassign them from rooms</p>
    </div>

    <div
      v-if="unassignedDwellers.length === 0"
      class="empty-state"
      :class="{ 'drop-zone-active': isDraggingOver }"
      @dragover="handleDropZoneDragOver"
      @dragleave="handleDropZoneDragLeave"
      @drop="handleDropZoneDrop"
    >
      <Icon v-if="!isDraggingOver" icon="mdi:check-circle" class="h-12 w-12 text-green-600" />
      <Icon v-else icon="mdi:arrow-down-bold" class="h-12 w-12 text-green-500 animate-bounce" />
      <p v-if="!isDraggingOver">All dwellers are assigned!</p>
      <p v-else class="drop-message">Drop to unassign</p>
    </div>

    <div
      v-else
      class="dweller-grid-container"
      @dragover="handleDropZoneDragOver"
      @dragleave="handleDropZoneDragLeave"
      @drop="handleDropZoneDrop"
    >
      <div
        v-if="isDraggingOver"
        class="drop-overlay"
      >
        <Icon icon="mdi:arrow-down-bold" class="h-12 w-12 animate-bounce" />
        <p>Drop to unassign</p>
      </div>

      <div class="dweller-grid">
        <div
          v-for="dweller in unassignedDwellers"
          :key="dweller.id"
          class="dweller-card"
          draggable="true"
          @dragstart="handleDragStart($event, dweller)"
          @dragend="handleDragEnd"
        >
        <div class="dweller-avatar">
          <img
            v-if="getImageUrl(dweller.thumbnail_url)"
            :src="getImageUrl(dweller.thumbnail_url)!"
            :alt="`${dweller.first_name} ${dweller.last_name}`"
            class="avatar-image"
          />
          <Icon v-else icon="mdi:account-circle" class="h-12 w-12 text-gray-400" />
        </div>

        <div class="dweller-info">
          <p class="dweller-name">{{ dweller.first_name }} {{ dweller.last_name }}</p>
          <p class="dweller-level">Level {{ dweller.level }}</p>

          <div class="dweller-stats">
            <div class="stat-item" title="Strength">
              <span class="stat-label">S</span>
              <span class="stat-value">{{ dweller.strength }}</span>
            </div>
            <div class="stat-item" title="Perception">
              <span class="stat-label">P</span>
              <span class="stat-value">{{ dweller.perception }}</span>
            </div>
            <div class="stat-item" title="Endurance">
              <span class="stat-label">E</span>
              <span class="stat-value">{{ dweller.endurance }}</span>
            </div>
            <div class="stat-item" title="Charisma">
              <span class="stat-label">C</span>
              <span class="stat-value">{{ dweller.charisma }}</span>
            </div>
            <div class="stat-item" title="Intelligence">
              <span class="stat-label">I</span>
              <span class="stat-value">{{ dweller.intelligence }}</span>
            </div>
            <div class="stat-item" title="Agility">
              <span class="stat-label">A</span>
              <span class="stat-value">{{ dweller.agility }}</span>
            </div>
            <div class="stat-item" title="Luck">
              <span class="stat-label">L</span>
              <span class="stat-value">{{ dweller.luck }}</span>
            </div>
          </div>
        </div>

          <div class="drag-indicator">
            <Icon icon="mdi:drag" class="h-5 w-5 text-gray-500" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.notification {
  position: fixed;
  top: 80px;
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

.unassigned-dwellers-panel {
  background: rgba(0, 0, 0, 0.6);
  border: 1px solid #00ff00;
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 1rem;
  font-family: 'Courier New', monospace;
}

.panel-header {
  margin-bottom: 1rem;
  border-bottom: 1px solid rgba(0, 255, 0, 0.3);
  padding-bottom: 0.5rem;
}

.panel-title {
  color: #00ff00;
  font-size: 1.25rem;
  font-weight: bold;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.count-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #00ff00;
  color: #000;
  font-size: 0.875rem;
  font-weight: bold;
  min-width: 24px;
  height: 24px;
  border-radius: 12px;
  padding: 0 0.5rem;
}

.panel-subtitle {
  color: rgba(0, 255, 0, 0.7);
  font-size: 0.875rem;
  margin-top: 0.25rem;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  color: rgba(0, 255, 0, 0.7);
  gap: 0.5rem;
  transition: all 0.3s ease;
  border: 2px dashed transparent;
  border-radius: 8px;
  min-height: 120px;
}

.empty-state.drop-zone-active {
  border-color: #00ff00;
  background: rgba(0, 255, 0, 0.1);
  box-shadow: 0 0 20px rgba(0, 255, 0, 0.3);
}

.drop-message {
  color: #00ff00;
  font-weight: bold;
  font-size: 1.125rem;
}

.dweller-grid-container {
  position: relative;
}

.drop-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 255, 0, 0.15);
  border: 3px dashed #00ff00;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #00ff00;
  font-size: 1.25rem;
  font-weight: bold;
  gap: 1rem;
  z-index: 10;
  pointer-events: none;
}

.dweller-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 0.75rem;
  max-height: 400px;
  overflow-y: auto;
  padding-right: 0.5rem;
}

.dweller-grid::-webkit-scrollbar {
  width: 8px;
}

.dweller-grid::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.3);
  border-radius: 4px;
}

.dweller-grid::-webkit-scrollbar-thumb {
  background: #00ff00;
  border-radius: 4px;
}

.dweller-grid::-webkit-scrollbar-thumb:hover {
  background: #00cc00;
}

.dweller-card {
  position: relative;
  background: rgba(0, 50, 0, 0.4);
  border: 1px solid rgba(0, 255, 0, 0.5);
  border-radius: 6px;
  padding: 0.75rem;
  cursor: grab;
  transition: all 0.2s ease;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.dweller-card:hover {
  border-color: #00ff00;
  background: rgba(0, 80, 0, 0.5);
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0, 255, 0, 0.2);
}

.dweller-card:active {
  cursor: grabbing;
  opacity: 0.7;
}

.dweller-avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 48px;
}

.avatar-image {
  width: 48px;
  height: 48px;
  object-fit: cover;
  border-radius: 50%;
  border: 2px solid #00ff00;
}

.dweller-info {
  flex: 1;
}

.dweller-name {
  color: #00ff00;
  font-weight: bold;
  font-size: 0.875rem;
  margin-bottom: 0.25rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dweller-level {
  color: rgba(0, 255, 0, 0.7);
  font-size: 0.75rem;
  margin-bottom: 0.5rem;
}

.dweller-stats {
  display: flex;
  gap: 0.25rem;
  flex-wrap: wrap;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  font-size: 0.625rem;
  min-width: 20px;
}

.stat-label {
  color: rgba(0, 255, 0, 0.6);
  font-weight: bold;
}

.stat-value {
  color: #00ff00;
  font-weight: bold;
  font-size: 0.75rem;
}

.drag-indicator {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  opacity: 0.5;
}

.dweller-card:hover .drag-indicator {
  opacity: 1;
}
</style>
