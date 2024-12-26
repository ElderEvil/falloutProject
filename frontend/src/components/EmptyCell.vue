<script setup lang="ts">
import { ref, computed } from 'vue'
import { NButton, NProgress } from 'naive-ui'
import { useVaultStore } from '@/stores/vault'
import type { GridPosition } from '@/types/grid.types'
import { getDigTime } from '@/types/grid.types'

const props = defineProps<{
  position: GridPosition
  status: 'empty' | 'digging' | 'ready' | 'occupied'
  canDig: boolean
}>()

const vaultStore = useVaultStore()
const progress = ref(0)
const digInterval = ref<number | null>(null)

const startDigging = () => {
  if (!props.canDig) return

  vaultStore.startDigging(props.position)
  const startTime = Date.now()
  const digTime = getDigTime(props.position.y)

  digInterval.value = window.setInterval(() => {
    const elapsed = Date.now() - startTime
    progress.value = Math.min((elapsed / digTime) * 100, 100)

    if (progress.value === 100) {
      clearInterval(digInterval.value!)
      vaultStore.completeDigging(props.position)
    }
  }, 50)
}

const statusText = computed(() => {
  switch (props.status) {
    case 'empty':
      return props.canDig ? 'DIG' : ''
    case 'digging':
      return 'DIGGING...'
    case 'ready':
      return 'CONSTRUCT'
    default:
      return ''
  }
})
</script>

<template>
  <div class="empty-cell">
    <div v-if="status === 'digging'" class="progress-container">
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
      <span class="status-text">{{ statusText }}</span>
    </div>
    <div v-else class="cell-content">
      <span class="coordinates">{{ position.x }},{{ position.y }}</span>
      <NButton v-if="status === 'empty' && canDig" @click="startDigging" class="dig-button">
        DIG
      </NButton>
      <NButton v-if="status === 'ready'" @click="$emit('construct')" class="construct-button">
        CONSTRUCT
      </NButton>
    </div>
  </div>
</template>

<style scoped>
.empty-cell {
  height: 100%;
  border: 1px dashed rgba(0, 255, 0, 0.3);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 16px;
  background: rgba(0, 255, 0, 0.02);
}

.cell-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  width: 100%;
  height: 100%;
  justify-content: center;
}

.coordinates {
  font-family: 'Courier New', monospace;
  color: rgba(0, 255, 0, 0.3);
  font-size: 0.8em;
}

.progress-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.progress-circle {
  width: 80px;
  height: 80px;
}

.progress-text {
  font-family: 'Courier New', monospace;
  font-size: 1.2em;
  font-weight: bold;
  color: var(--theme-text);
  text-shadow: 0 0 10px var(--theme-shadow);
}

.status-text {
  font-family: 'Courier New', monospace;
  color: var(--theme-text);
  font-size: 0.9em;
  text-shadow: 0 0 8px var(--theme-shadow);
}

.dig-button,
.construct-button {
  min-width: 120px;
  font-weight: bold;
  text-shadow: 0 0 8px var(--theme-shadow);
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
