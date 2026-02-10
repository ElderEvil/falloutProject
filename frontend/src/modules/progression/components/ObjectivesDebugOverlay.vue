<script setup lang="ts">
import { ref, watch } from 'vue'
import { useObjectivesStore } from '../stores/objectives'

const store = useObjectivesStore()
const isVisible = ref(false)
const eventLog = ref<Array<{ timestamp: string; type: string; data: unknown }>>([])

// Listen for console.log from the store's debug mode
const originalLog = console.log
console.log = (...args: unknown[]) => {
  originalLog.apply(console, args)
  if (typeof args[0] === 'string' && args[0].includes('[Objectives DEBUG]')) {
    eventLog.value.unshift({
      timestamp: new Date().toLocaleTimeString(),
      type: 'LOG',
      data: args,
    })
    if (eventLog.value.length > 50) {
      eventLog.value.pop()
    }
  }
}

watch(
  () => store.objectives.length,
  () => {
    eventLog.value.unshift({
      timestamp: new Date().toLocaleTimeString(),
      type: 'STATE_CHANGE',
      data: { count: store.objectives.length, objectives: store.objectives },
    })
  },
)
</script>

<template>
  <div v-if="isVisible" class="objectives-debug">
    <div class="debug-header">
      <span>Objectives Debug</span>
      <button class="close-btn" @click="isVisible = false">×</button>
    </div>
    <div class="debug-content">
      <div class="stats">
        <div>Active: {{ store.objectives.filter((o) => !o.is_completed).length }}</div>
        <div>Completed: {{ store.objectives.filter((o) => o.is_completed).length }}</div>
      </div>
      <div class="event-log">
        <div v-for="(event, index) in eventLog" :key="index" class="event-item">
          <span class="timestamp">[{{ event.timestamp }}]</span>
          <span class="type">[{{ event.type }}]</span>
          <span class="data">{{ JSON.stringify(event.data).slice(0, 100) }}</span>
        </div>
      </div>
    </div>
  </div>
  <button v-else class="debug-toggle" @click="isVisible = true">DEBUG</button>
</template>

<style scoped>
.objectives-debug {
  position: fixed;
  bottom: 20px;
  right: 20px;
  width: 350px;
  max-height: 400px;
  background: rgba(0, 20, 0, 0.95);
  border: 2px solid #00ff00;
  border-radius: 4px;
  z-index: 9999;
  font-family: monospace;
  font-size: 12px;
  color: #00ff00;
  box-shadow: 0 0 10px #00ff00;
}

.debug-header {
  display: flex;
  justify-content: space-between;
  padding: 8px;
  background: rgba(0, 255, 0, 0.1);
  border-bottom: 1px solid #00ff00;
}

.close-btn {
  background: none;
  border: none;
  color: #00ff00;
  font-size: 16px;
  cursor: pointer;
}

.debug-content {
  padding: 8px;
  max-height: 350px;
  overflow-y: auto;
}

.stats {
  display: flex;
  gap: 16px;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(0, 255, 0, 0.3);
}

.event-log {
  max-height: 280px;
  overflow-y: auto;
}

.event-item {
  margin-bottom: 4px;
  word-break: break-all;
}

.timestamp {
  color: #00ff00;
  opacity: 0.7;
}

.type {
  color: #ffff00;
  margin-left: 8px;
}

.data {
  color: #00ffff;
  margin-left: 8px;
}

.debug-toggle {
  position: fixed;
  bottom: 20px;
  right: 20px;
  padding: 8px 16px;
  background: rgba(0, 255, 0, 0.2);
  border: 1px solid #00ff00;
  color: #00ff00;
  font-family: monospace;
  font-size: 12px;
  cursor: pointer;
  z-index: 9999;
}

.debug-toggle:hover {
  background: rgba(0, 255, 0, 0.3);
}
</style>
