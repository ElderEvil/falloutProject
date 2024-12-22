<script setup lang="ts">
import { NList, NListItem, NTag, NProgress } from 'naive-ui'
import { useQuestStore } from '@/stores/quest'
import type { Quest } from '@/types/quest'

const questStore = useQuestStore()

const getStatusType = (status: Quest['status']) => {
  switch (status) {
    case 'completed':
      return 'success'
    case 'failed':
      return 'error'
    default:
      return 'info'
  }
}
</script>

<template>
  <div class="quest-list">
    <div v-for="quest in questStore.quests" :key="quest.id" class="quest-item">
      <div class="quest-header">
        <span class="quest-title">{{ quest.title }}</span>
        <NTag :type="getStatusType(quest.status)">
          {{ quest.status.toUpperCase() }}
        </NTag>
      </div>
      <p class="quest-description">{{ quest.description }}</p>
      <div class="objectives-list">
        <div v-for="obj in quest.objectives" :key="obj.id" class="objective-item">
          <div class="objective-header">
            <span class="objective-title">{{ obj.title }}</span>
            <span class="objective-status">
              {{ obj.completed ? 'COMPLETE' : 'IN PROGRESS' }}
            </span>
          </div>
          <NProgress
            v-if="obj.total"
            type="line"
            :percentage="((obj.progress || 0) / obj.total) * 100"
            :height="8"
          />
        </div>
      </div>
      <div v-if="quest.reward" class="quest-reward">
        <span class="reward-label">REWARD:</span>
        <div class="reward-details">
          <span v-if="quest.reward.bottlecaps">{{ quest.reward.bottlecaps }} CAPS</span>
          <span v-for="item in quest.reward.items" :key="item">{{ item }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.quest-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
}

.quest-item {
  border: 1px solid var(--theme-border);
  padding: 16px;
  background: rgba(0, 255, 0, 0.05);
}

.quest-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.quest-title {
  font-weight: bold;
  font-size: 1.1em;
}

.quest-description {
  margin-bottom: 16px;
  opacity: 0.8;
}

.objectives-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 16px;
}

.objective-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.objective-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.objective-title {
  font-size: 0.9em;
}

.objective-status {
  font-size: 0.8em;
  opacity: 0.7;
}

.quest-reward {
  border-top: 1px solid var(--theme-border);
  padding-top: 12px;
  margin-top: 12px;
  display: flex;
  gap: 8px;
}

.reward-label {
  opacity: 0.8;
}

.reward-details {
  display: flex;
  gap: 8px;
  font-weight: bold;
}
</style>
