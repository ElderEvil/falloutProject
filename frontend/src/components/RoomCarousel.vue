<script setup lang="ts">
import { ref } from 'vue'
import { NCard, NButton, useMessage } from 'naive-ui'
import { useVaultStore } from '@/stores/vault'
import type { Room } from '@/types/vault'

const vaultStore = useVaultStore()
const message = useMessage()
const currentIndex = ref(0)

const roomTypes = [
  {
    type: 'power' as const,
    label: 'POWER GENERATOR',
    description: 'Generates power for vault operations'
  },
  { type: 'water' as const, label: 'WATER TREATMENT', description: 'Processes and purifies water' },
  {
    type: 'food' as const,
    label: 'FOOD PRODUCTION',
    description: 'Produces food for vault dwellers'
  },
  { type: 'living' as const, label: 'LIVING QUARTERS', description: 'Housing for vault dwellers' }
]

const handleAddRoom = (type: Room['type']) => {
  if (vaultStore.addRoom(type)) {
    message.success('Room constructed successfully')
  } else {
    message.error('Cannot construct more rooms')
  }
}

const nextRoom = () => {
  currentIndex.value = (currentIndex.value + 1) % roomTypes.length
}

const prevRoom = () => {
  currentIndex.value = (currentIndex.value - 1 + roomTypes.length) % roomTypes.length
}
</script>

<template>
  <div class="room-carousel">
    <NButton class="nav-button" @click="prevRoom">←</NButton>
    <NCard class="room-card">
      <div class="room-info">
        <h3>{{ roomTypes[currentIndex].label }}</h3>
        <p>{{ roomTypes[currentIndex].description }}</p>
        <NButton
          type="primary"
          @click="handleAddRoom(roomTypes[currentIndex].type)"
          class="construct-button"
        >
          CONSTRUCT
        </NButton>
      </div>
    </NCard>
    <NButton class="nav-button" @click="nextRoom">→</NButton>
  </div>
</template>

<style scoped>
.room-carousel {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
}

.room-card {
  flex: 1;
  border: 2px solid #00ff00;
  min-height: 150px;
}

.room-info {
  text-align: center;
}

.room-info h3 {
  margin: 0 0 12px 0;
  font-family: 'Courier New', Courier, monospace;
}

.room-info p {
  margin: 0 0 16px 0;
  opacity: 0.8;
}

.nav-button {
  width: 40px;
  height: 40px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
}

.construct-button {
  min-width: 120px;
}
</style>
