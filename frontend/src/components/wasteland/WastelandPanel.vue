<script setup lang="ts">
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useDwellerStore } from '@/stores/dweller'
import { Icon } from '@iconify/vue'

const authStore = useAuthStore()
const dwellerStore = useDwellerStore()

const isDraggingOver = ref(false)
const sendError = ref<string | null>(null)
const sendSuccess = ref<string | null>(null)

const handleDragOver = (event: DragEvent) => {
  event.preventDefault()
  event.dataTransfer!.dropEffect = 'move'
  isDraggingOver.value = true
}

const handleDragLeave = () => {
  isDraggingOver.value = false
}

const handleDrop = async (event: DragEvent) => {
  event.preventDefault()
  isDraggingOver.value = false
  sendError.value = null
  sendSuccess.value = null

  try {
    const data = JSON.parse(event.dataTransfer!.getData('application/json'))
    const { dwellerId, firstName, lastName, currentRoomId } = data

    // If dweller is assigned to a room, unassign them first
    if (currentRoomId) {
      await dwellerStore.unassignDwellerFromRoom(dwellerId, authStore.token as string)
    }

    // TODO: When wasteland exploration API is ready, send them to wasteland
    // For now, just unassign them
    sendSuccess.value = `${firstName} ${lastName} sent to wasteland! (Feature coming soon)`

    setTimeout(() => {
      sendSuccess.value = null
    }, 4000)
  } catch (error) {
    console.error('Failed to send dweller to wasteland:', error)
    sendError.value = 'Failed to send dweller to wasteland'
    setTimeout(() => {
      sendError.value = null
    }, 3000)
  }
}
</script>

<template>
  <div class="wasteland-panel">
    <!-- Success/Error notifications -->
    <div v-if="sendSuccess" class="notification notification-success">
      <Icon icon="mdi:check-circle" class="h-5 w-5" />
      {{ sendSuccess }}
    </div>
    <div v-if="sendError" class="notification notification-error">
      <Icon icon="mdi:alert-circle" class="h-5 w-5" />
      {{ sendError }}
    </div>

    <div
      class="wasteland-dropzone"
      :class="{ 'drag-over': isDraggingOver }"
      @dragover="handleDragOver"
      @dragleave="handleDragLeave"
      @drop="handleDrop"
    >
      <div class="dropzone-content">
        <Icon icon="mdi:map-marker-radius" class="dropzone-icon" />
        <h3 class="dropzone-title">The Wasteland</h3>
        <p class="dropzone-subtitle">Drag dwellers here to send them exploring</p>
        <div v-if="isDraggingOver" class="drop-indicator">
          <Icon icon="mdi:arrow-down-bold" class="h-8 w-8 animate-bounce" />
          <span>Release to send!</span>
        </div>
      </div>

      <!-- TODO: Display exploring dwellers when API is ready -->
      <div class="exploring-dwellers">
        <p class="text-xs text-gray-500">
          <Icon icon="mdi:information" class="inline h-4 w-4" />
          Wasteland exploration coming soon!
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.wasteland-panel {
  position: relative;
  margin-bottom: 1rem;
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

.wasteland-dropzone {
  background: rgba(139, 69, 19, 0.2);
  border: 2px dashed rgba(205, 133, 63, 0.5);
  border-radius: 8px;
  padding: 1.5rem;
  transition: all 0.3s ease;
  min-height: 150px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  cursor: pointer;
}

.wasteland-dropzone:hover {
  border-color: rgba(205, 133, 63, 0.8);
  background: rgba(139, 69, 19, 0.3);
}

.wasteland-dropzone.drag-over {
  border-color: #00ff00;
  border-width: 3px;
  border-style: solid;
  background: rgba(0, 255, 0, 0.1);
  box-shadow: 0 0 20px rgba(0, 255, 0, 0.4);
  transform: scale(1.02);
}

.dropzone-content {
  text-align: center;
  position: relative;
}

.dropzone-icon {
  font-size: 3rem;
  color: rgba(205, 133, 63, 0.8);
  margin-bottom: 0.5rem;
}

.drag-over .dropzone-icon {
  color: #00ff00;
}

.dropzone-title {
  color: rgba(205, 133, 63, 1);
  font-size: 1.5rem;
  font-weight: bold;
  font-family: 'Courier New', monospace;
  margin-bottom: 0.25rem;
}

.drag-over .dropzone-title {
  color: #00ff00;
}

.dropzone-subtitle {
  color: rgba(205, 133, 63, 0.7);
  font-size: 0.875rem;
  font-family: 'Courier New', monospace;
}

.drag-over .dropzone-subtitle {
  display: none;
}

.drop-indicator {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  color: #00ff00;
  font-size: 1rem;
  font-weight: bold;
  pointer-events: none;
}

.exploring-dwellers {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid rgba(205, 133, 63, 0.3);
  text-align: center;
}
</style>
