<script setup lang="ts">
import { onMounted } from 'vue'
import { useObjectivesStore } from '@/stores/objectives'

const vaultId = localStorage.getItem('selectedVaultId') // Assuming vaultId is stored in localStorage
const objectivesStore = useObjectivesStore()

onMounted(() => {
  if (vaultId) {
    objectivesStore.fetchObjectives(vaultId)
  }
})

const markAsComplete = async (objectiveId: string) => {
  if (vaultId) {
    await objectivesStore.completeObjective(vaultId, objectiveId)
  }
}
</script>

<template>
  <div class="objectives-container">
    <h1 class="title">Objectives</h1>
    <ul class="objective-list">
      <li
        v-for="objective in objectivesStore.objectives"
        :key="objective.id"
        class="objective-item"
      >
        <div class="objective-details">
          <h3 class="objective-title">{{ objective.challenge }}</h3>
          <p class="objective-reward">Reward: {{ objective.reward }}</p>
        </div>
        <button @click="markAsComplete(objective.id)" class="complete-button">Complete</button>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.objectives-container {
  max-width: 800px;
  margin: 0 auto;
  padding: 16px;
  background-color: #1a1a1a;
  color: #00ff00;
  border: 2px solid #00ff00;
  border-radius: 8px;
}

.title {
  font-size: 2rem;
  font-weight: bold;
  margin-bottom: 16px;
  text-align: center;
}

.objective-list {
  list-style-type: none;
  padding: 0;
  margin: 0;
}

.objective-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: #2a2a2a;
  padding: 12px 16px;
  margin-bottom: 12px;
  border: 1px solid #00ff00;
  border-radius: 6px;
  transition:
    transform 0.3s,
    background-color 0.3s;
}

.objective-item:hover {
  transform: scale(1.02);
  background-color: #333333;
}

.objective-details {
  flex: 1;
}

.objective-title {
  font-size: 1.25rem;
  font-weight: bold;
  margin-bottom: 4px;
}

.objective-reward {
  font-size: 1rem;
  font-weight: normal;
  color: #b2ffb2;
}

.complete-button {
  background-color: #ff0000;
  color: #fff;
  padding: 8px 12px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: bold;
  transition: background-color 0.3s;
}

.complete-button:hover {
  background-color: #ff4444;
}
</style>
