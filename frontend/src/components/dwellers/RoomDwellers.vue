<script setup lang="ts">
import { computed } from 'vue'
import { useDwellerStore } from '@/stores/dweller'
import { Icon } from '@iconify/vue'
import type { DwellerShort } from '@/models/dweller'
import DwellerStatusBadge from './DwellerStatusBadge.vue'

interface Props {
  roomId: string
}

const props = defineProps<Props>()
const dwellerStore = useDwellerStore()

const emit = defineEmits<{
  dragStart: [dweller: DwellerShort]
  dragEnd: []
}>()

// Get dwellers assigned to this room
const roomDwellers = computed(() => {
  return dwellerStore.dwellers.filter(dweller => dweller.room_id === props.roomId)
})

const handleDragStart = (event: DragEvent, dweller: DwellerShort) => {
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('application/json', JSON.stringify({
      dwellerId: dweller.id,
      firstName: dweller.first_name,
      lastName: dweller.last_name,
      currentRoomId: props.roomId
    }))
  }
  emit('dragStart', dweller)
}

const handleDragEnd = () => {
  emit('dragEnd')
}

const getImageUrl = (imagePath: string | null) => {
  if (!imagePath) return null
  return imagePath.startsWith('http') ? imagePath : `http://${imagePath}`
}
</script>

<template>
  <div v-if="roomDwellers.length > 0" class="room-dwellers">
    <div
      v-for="dweller in roomDwellers"
      :key="dweller.id"
      class="dweller-avatar"
      draggable="true"
      @dragstart="handleDragStart($event, dweller)"
      @dragend="handleDragEnd"
      :title="`${dweller.first_name} ${dweller.last_name} (Lv${dweller.level})`"
    >
      <img
        v-if="getImageUrl(dweller.thumbnail_url)"
        :src="getImageUrl(dweller.thumbnail_url)!"
        :alt="`${dweller.first_name} ${dweller.last_name}`"
        class="avatar-image"
      />
      <Icon v-else icon="mdi:account-circle" class="h-8 w-8 text-green-500" />
      <div class="dweller-level">{{ dweller.level }}</div>
      <div class="status-indicator">
        <DwellerStatusBadge :status="dwellerStore.getDwellerStatus(dweller.id)" size="small" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.room-dwellers {
  display: flex;
  gap: 0.25rem;
  flex-wrap: wrap;
  margin-top: 0.5rem;
  padding: 0.25rem;
}

.dweller-avatar {
  position: relative;
  width: 32px;
  height: 32px;
  cursor: grab;
  transition: transform 0.2s;
  border: 1px solid rgba(0, 255, 0, 0.5);
  border-radius: 4px;
  overflow: hidden;
}

.dweller-avatar:hover {
  transform: scale(1.1);
  border-color: #00ff00;
  box-shadow: 0 0 8px rgba(0, 255, 0, 0.5);
}

.dweller-avatar:active {
  cursor: grabbing;
  opacity: 0.7;
}

.avatar-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.dweller-level {
  position: absolute;
  bottom: 0;
  right: 0;
  background: rgba(0, 0, 0, 0.8);
  color: #00ff00;
  font-size: 0.625rem;
  font-weight: bold;
  padding: 0 2px;
  line-height: 1;
  border-top-left-radius: 2px;
}

.status-indicator {
  position: absolute;
  top: 0;
  left: 0;
  opacity: 0;
  transition: opacity 0.2s;
  z-index: 10;
}

.dweller-avatar:hover .status-indicator {
  opacity: 1;
}
</style>
