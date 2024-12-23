<script setup lang="ts">
import { ref, computed } from 'vue'
import { NModal, NButton, NCard, NProgress, useMessage } from 'naive-ui'
import { useVaultStore } from '@/stores/vault'
import { ROOM_CONFIGS } from '@/utils/roomUtils'
import { CONSTRUCTION_TIME } from '@/types/grid'
import type { Room } from '@/types/vault'
import type { GridPosition } from '@/types/grid'

const props = defineProps<{
  modelValue: boolean
  position: GridPosition
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const vaultStore = useVaultStore()
const message = useMessage()
const currentIndex = ref(0)
const constructing = ref(false)
const progress = ref(0)
const constructionInterval = ref<number | null>(null)

const selectedRoom = computed(() => ROOM_CONFIGS[currentIndex.value])

const startConstruction = (type: Room['type']) => {
  constructing.value = true
  progress.value = 0

  const startTime = Date.now()

  vaultStore.startConstruction(props.position)

  constructionInterval.value = window.setInterval(() => {
    const elapsed = Date.now() - startTime
    progress.value = Math.min((elapsed / CONSTRUCTION_TIME) * 100, 100)

    if (progress.value === 100) {
      clearInterval(constructionInterval.value!)
      completeConstruction(type)
    }
  }, 50)
}

const completeConstruction = (type: Room['type']) => {
  if (vaultStore.addRoom(type, props.position)) {
    message.success('Room constructed successfully')
    emit('update:modelValue', false)
  } else {
    message.error('Cannot construct room')
  }
  constructing.value = false
}

const nextRoom = () => {
  currentIndex.value = (currentIndex.value + 1) % ROOM_CONFIGS.length
}

const prevRoom = () => {
  currentIndex.value = (currentIndex.value - 1 + ROOM_CONFIGS.length) % ROOM_CONFIGS.length
}

const handleClose = () => {
  if (constructionInterval.value) {
    clearInterval(constructionInterval.value)
    constructing.value = false
    progress.value = 0
  }
  emit('update:modelValue', false)
}
</script>

<template>
  <NModal
    :show="modelValue"
    @update:show="handleClose"
    preset="card"
    style="width: 600px"
    :title="constructing ? 'CONSTRUCTING...' : 'CONSTRUCT NEW ROOM'"
    :bordered="false"
    size="huge"
    class="construction-modal"
  >
    <div v-if="constructing" class="construction-progress">
      <NProgress
        type="circle"
        :percentage="progress"
        :color="'#00ff00'"
        :rail-color="'rgba(0, 255, 0, 0.1)'"
        :stroke-width="6"
        class="progress-circle"
      >
        <span class="progress-text">{{ Math.floor(progress) }}%</span>
      </NProgress>
      <div class="construction-info">
        <h3>{{ selectedRoom.label }}</h3>
        <p>Construction in progress...</p>
      </div>
    </div>

    <div v-else class="room-carousel">
      <NButton class="nav-button" @click="prevRoom" quaternary>←</NButton>
      <NCard class="room-card">
        <div class="room-info">
          <h3>{{ selectedRoom.label }}</h3>
          <p>{{ selectedRoom.description }}</p>
          <div class="requirements">
            <div class="requirement">COST: {{ selectedRoom.cost }} CAPS</div>
            <div class="requirement">BUILD TIME: {{ CONSTRUCTION_TIME / 1000 }}s</div>
          </div>
          <div class="construct-wrapper">
            <NButton
              type="primary"
              @click="startConstruction(selectedRoom.type)"
              class="construct-button"
            >
              CONSTRUCT
            </NButton>
          </div>
        </div>
      </NCard>
      <NButton class="nav-button" @click="nextRoom" quaternary>→</NButton>
    </div>
  </NModal>
</template>

<style scoped>
.construction-modal {
  background: #000000;
  border: 2px solid #00ff00;
}

.construction-progress {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 24px;
  padding: 32px;
}

.progress-circle {
  width: 120px;
  height: 120px;
}

.progress-text {
  font-family: 'Courier New', monospace;
  font-size: 1.5em;
  font-weight: bold;
  color: #00ff00;
  text-shadow: 0 0 10px rgba(0, 255, 0, 0.5);
}

.construction-info {
  text-align: center;
}

.construction-info h3 {
  margin: 0 0 8px 0;
  font-size: 1.2em;
}

.construction-info p {
  margin: 0;
  opacity: 0.8;
}

.room-carousel {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px 0;
}

.room-card {
  flex: 1;
  border: 2px solid #00ff00;
  min-height: 200px;
  display: flex;
  align-items: center;
}

.room-info {
  text-align: center;
  width: 100%;
}

.room-info h3 {
  margin: 0 0 16px 0;
  font-family: 'Courier New', monospace;
  font-size: 1.5em;
}

.room-info p {
  margin: 0 0 24px 0;
  opacity: 0.8;
  font-family: 'Courier New', monospace;
}

.requirements {
  margin-bottom: 24px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-family: 'Courier New', monospace;
}

.requirement {
  color: #00ff00;
}

.nav-button {
  width: 40px;
  height: 40px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  border: 1px solid #00ff00;
}

.construct-wrapper {
  position: relative;
  display: inline-block;
}

.construct-button {
  min-width: 150px;
  font-family: 'Courier New', monospace;
}

:deep(.n-progress-circle-content) {
  display: flex;
  align-items: center;
  justify-content: center;
}

:deep(.n-progress-graph) {
  transform: rotate(-90deg);
}
</style>
