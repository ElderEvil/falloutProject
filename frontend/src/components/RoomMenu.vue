<script setup>
import { ref } from 'vue'
import { useRoomStore } from '@/stores/room'
import LockIcon from '@/components/icons/LockIcon.vue'

const roomStore = useRoomStore()
const availableRooms = ref(roomStore.availableRooms)

const emit = defineEmits(['roomSelected', 'close'])

const selectRoom = (room) => {
  emit('roomSelected', room)
}

const closeModal = () => {
  emit('close')
}
</script>

<template>
  <div class="modal-overlay" @click.self="closeModal">
    <div class="modal-content">
      <h2 class="mb-4 text-2xl">Select a Room to Build</h2>
      <ul class="flex space-x-4 overflow-x-auto">
        <li
          v-for="room in availableRooms"
          :key="room.id"
          @click="selectRoom(room)"
          class="cursor-pointer rounded bg-gray-700 p-2 text-white"
        >
          <div class="flex flex-col items-center">
            <div class="flex items-center space-x-2">
              <div>{{ room.name }}</div>
              <div v-if="room.population_required > 0">
                <LockIcon />
              </div>
            </div>
            <div class="my-2">
              <img
                :src="room.thumbnail_url"
                alt="Room Thumbnail"
                class="h-12 w-12 rounded-full object-cover"
              />
            </div>
            <div class="text-sm">Population required: {{ room.population_required }}</div>
          </div>
        </li>
      </ul>
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
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.modal-content {
  background: #222;
  border: 1px solid #00ff00;
  padding: 20px;
  max-width: 90%;
  max-height: 90%;
  overflow-y: auto;
}

.modal-content ul {
  display: flex;
  overflow-x: auto;
}

.modal-content li {
  flex-shrink: 0;
  min-width: 150px; /* Adjust as needed */
  text-align: center;
}
</style>
