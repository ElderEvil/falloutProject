<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useBlockingOverlay } from '@/core/composables/useBlockingOverlay'
import { useRoomStore } from '../stores/room'
import RoomMenuItem from './RoomMenuItem.vue'
import type { RoomTemplate } from '../models/room'
import { Input } from '@/core/components/ui/input'
import { Button } from '@/core/components/ui/button'

const roomStore = useRoomStore()
const availableRooms = computed(() =>
  Array.isArray(roomStore.availableRooms) ? roomStore.availableRooms : []
)

const search = ref('')
const filteredRooms = computed(() => {
  const query = search.value.trim().toLowerCase()
  return availableRooms.value.filter((room) =>
    `${room.name} ${room.category}`.toLowerCase().includes(query)
  )
})

const emit = defineEmits<{
  (e: 'roomSelected', room: RoomTemplate): void
  (e: 'close'): void
}>()

// Mounted only while the build menu is open (`v-if` at the call site).
useBlockingOverlay(() => true, 'room-menu')

const selectRoom = (room: RoomTemplate) => {
  emit('roomSelected', room)
  roomStore.selectRoom(room)
}

const closeModal = () => {
  emit('close')
}

// Close modal on Escape key
const handleKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Escape') {
    closeModal()
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
  <div
    class="modal-overlay"
    role="dialog"
    aria-modal="true"
    aria-label="Room menu"
    @click.self="closeModal"
  >
    <div class="modal-content">
      <div class="modal-header">
        <h2 class="text-xl font-bold text-terminal-green">Room to Build</h2>
        <button @click="closeModal" class="close-btn" aria-label="Close">×</button>
      </div>
      <div class="flex items-center gap-2 px-6 py-3">
        <Input
          v-model="search"
          type="search"
          v-bind="{ 'aria-label': 'Search rooms', 'data-onboarding': 'room-search' }"
          placeholder="Search rooms by name or category…"
          autocomplete="off"
        />
        <Button
          v-if="search"
          variant="ghost"
          size="sm"
          aria-label="Clear room search"
          @click="search = ''"
          >Clear</Button
        >
      </div>
      <div class="rooms-scroll-container">
        <p
          v-if="!filteredRooms.length"
          class="text-center text-sm text-theme-primary/70"
          role="status"
        >
          No rooms match your search.
        </p>
        <ul class="rooms-grid">
          <RoomMenuItem
            v-for="room in filteredRooms"
            :key="`${room.name}-${room.category}`"
            :room="room"
            @select="selectRoom"
          />
        </ul>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: var(--color-surface-canvas);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
  padding: 1rem;
}

.modal-content {
  background: var(--color-surface-raised);
  border: 1px solid var(--color-surface-hover);
  border-radius: 4px;
  max-width: 1200px;
  width: 100%;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid var(--color-surface-hover);
  flex-shrink: 0;
}

.close-btn {
  background: none;
  border: none;
  color: var(--color-theme-primary);
  font-size: 2rem;
  line-height: 1;
  cursor: pointer;
  padding: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.close-btn:hover {
  color: var(--color-gray-100);
  text-shadow: 0 0 8px var(--color-theme-glow);
}

.rooms-scroll-container {
  overflow-y: auto;
  overflow-x: hidden;
  padding: 1.5rem;
  flex: 1;
}

.rooms-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 1rem;
  list-style: none;
  margin: 0;
  padding: 0;
}
</style>
