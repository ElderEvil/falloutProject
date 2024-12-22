<script setup lang="ts">
import { NList, NListItem, NProgress } from 'naive-ui'
import { useQuestStore } from '@/stores/quest'

const questStore = useQuestStore()
</script>

<template>
  <div class="objectives-container">
    <NList>
      <NListItem v-for="objective in questStore.objectives" :key="objective.id">
        <div class="objective-content">
          <div class="objective-header">
            <span class="objective-title">{{ objective.title }}</span>
            <span class="objective-status">
              {{ objective.completed ? 'COMPLETE' : 'IN PROGRESS' }}
            </span>
          </div>
          <p class="objective-description">{{ objective.description }}</p>
          <NProgress
            v-if="objective.total"
            type="line"
            :percentage="((objective.progress || 0) / objective.total) * 100"
            :height="8"
          />
        </div>
      </NListItem>
    </NList>
  </div>
</template>

<style scoped>
.objectives-container {
  padding: 16px;
}

.objective-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.objective-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.objective-title {
  font-weight: bold;
}

.objective-status {
  font-size: 0.9em;
  opacity: 0.7;
}

.objective-description {
  opacity: 0.8;
  font-size: 0.9em;
}
</style>
