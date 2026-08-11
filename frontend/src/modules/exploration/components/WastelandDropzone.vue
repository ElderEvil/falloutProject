<script setup lang="ts">
import { ref } from 'vue'
import { Icon } from '@iconify/vue'

interface DropDwellerPayload {
  dwellerId: string
  firstName: string
  lastName: string
  currentRoomId?: string
}

const emit = defineEmits<{
  'drop-dweller': [payload: DropDwellerPayload]
  'drop-error': [message: string]
}>()

const isDraggingOver = ref(false)

const handleDragOver = (event: DragEvent) => {
  event.preventDefault()
  event.dataTransfer!.dropEffect = 'move'
  isDraggingOver.value = true
}

const handleDragLeave = () => {
  isDraggingOver.value = false
}

const handleDrop = (event: DragEvent) => {
  event.preventDefault()
  isDraggingOver.value = false

  try {
    const data = JSON.parse(event.dataTransfer!.getData('application/json'))
    const { dwellerId, firstName, lastName, currentRoomId } = data
    emit('drop-dweller', { dwellerId, firstName, lastName, currentRoomId })
  } catch {
    emit('drop-error', 'Failed to send dweller to wasteland')
  }
}
</script>

<template>
  <div
    class="wasteland-dropzone flex min-h-20 cursor-pointer flex-col justify-start rounded-lg border-2 border-dashed border-[rgba(205,133,63,0.5)] bg-[rgba(139,69,19,0.2)] p-4 transition-all duration-300 hover:border-[rgba(205,133,63,0.8)] hover:bg-[rgba(139,69,19,0.3)]"
    :class="isDraggingOver
      ? 'drag-over scale-[1.02] border-solid !border-theme-primary !border-[3px] !bg-theme-glow shadow-[0_0_20px_var(--color-theme-glow)]'
      : ''"
    @dragover="handleDragOver"
    @dragleave="handleDragLeave"
    @drop="handleDrop"
  >
    <div class="relative">
      <div class="flex items-center gap-4">
        <Icon
          icon="mdi:map-marker-radius"
          class="h-8 w-8 shrink-0"
          :class="isDraggingOver ? 'text-theme-primary' : 'text-[rgba(205,133,63,0.8)]'"
        />
        <div>
          <h3
            class="mb-0.5 font-mono text-lg font-bold"
            :class="isDraggingOver ? 'text-theme-primary' : 'text-[rgba(205,133,63,1)]'"
          >
            The Wasteland
          </h3>
          <p
            v-if="!isDraggingOver"
            class="font-mono text-xs text-[rgba(205,133,63,0.7)]"
          >
            Drag dwellers here to send them exploring
          </p>
        </div>
      </div>
      <div
        v-if="isDraggingOver"
        class="drop-indicator pointer-events-none absolute inset-0 flex flex-col items-center justify-center gap-2 text-base font-bold text-theme-primary"
      >
        <Icon icon="mdi:arrow-down-bold" class="h-8 w-8 animate-bounce" />
        <span>Release to send!</span>
      </div>
    </div>
    <slot />
  </div>
</template>
