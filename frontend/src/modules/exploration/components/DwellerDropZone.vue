<script setup lang="ts">
interface DwellerDropData {
  dwellerId: string
  firstName: string
  lastName: string
  currentRoomId?: string
}

defineProps<{
  isDraggingOver: boolean
}>()

const emit = defineEmits<{
  drop: [data: DwellerDropData]
  dragLeave: []
}>()

const handleDragOver = (event: DragEvent) => {
  event.preventDefault()
  event.dataTransfer!.dropEffect = 'move'
}

const handleDragLeave = () => {
  emit('dragLeave')
}

const handleDrop = (event: DragEvent) => {
  event.preventDefault()
  emit('dragLeave')

  try {
    const data = JSON.parse(event.dataTransfer!.getData('application/json')) as DwellerDropData
    emit('drop', data)
  } catch {
    console.error('Failed to parse dweller data')
  }
}
</script>

<template>
  <div
    class="wasteland-dropzone"
    :class="{ 'drag-over': isDraggingOver }"
    @dragover="handleDragOver"
    @dragleave="handleDragLeave"
    @drop="handleDrop"
  >
    <div class="dropzone-content">
      <div class="dropzone-header">
        <Icon icon="mdi:map-marker-radius" class="dropzone-icon" />
        <div>
          <h3 class="dropzone-title">The Wasteland</h3>
          <p class="dropzone-subtitle">Drag dwellers here to send them exploring</p>
        </div>
      </div>
      <div v-if="isDraggingOver" class="drop-indicator">
        <Icon icon="mdi:arrow-down-bold" class="h-8 w-8 animate-bounce" />
        <span>Release to send!</span>
      </div>
    </div>

    <slot />
  </div>
</template>

<style scoped>
.wasteland-dropzone {
  background: rgba(139, 69, 19, 0.2);
  border: 2px dashed rgba(205, 133, 63, 0.5);
  border-radius: 8px;
  padding: 1rem;
  transition: all 0.3s ease;
  min-height: 80px;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  cursor: pointer;
}

.wasteland-dropzone:hover {
  border-color: rgba(205, 133, 63, 0.8);
  background: rgba(139, 69, 19, 0.3);
}

.wasteland-dropzone.drag-over {
  border-color: var(--color-theme-primary);
  border-width: 3px;
  border-style: solid;
  background: var(--color-theme-glow);
  box-shadow: 0 0 20px var(--color-theme-glow);
  transform: scale(1.02);
}

.dropzone-content {
  position: relative;
}

.dropzone-header {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.dropzone-icon {
  font-size: 2rem;
  color: rgba(205, 133, 63, 0.8);
  flex-shrink: 0;
}

.drag-over .dropzone-icon {
  color: var(--color-theme-primary);
}

.dropzone-title {
  color: rgba(205, 133, 63, 1);
  font-size: 1.125rem;
  font-weight: bold;
  font-family: 'Courier New', monospace;
  margin-bottom: 0.125rem;
}

.drag-over .dropzone-title {
  color: var(--color-theme-primary);
}

.dropzone-subtitle {
  color: rgba(205, 133, 63, 0.7);
  font-size: 0.75rem;
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
  color: var(--color-theme-primary);
  font-size: 1rem;
  font-weight: bold;
  pointer-events: none;
}
</style>
