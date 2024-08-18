<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useObjectivesStore } from '@/stores/objectives'

const vaultId = localStorage.getItem('selectedVaultId') // Assuming vaultId is stored in localStorage
const objectivesStore = useObjectivesStore()
const activeTab = ref('notCompleted')

onMounted(() => {
  if (vaultId) {
    objectivesStore.fetchObjectives(vaultId)
  }
})

const filterObjectives = (status: boolean) => {
  return objectivesStore.objectives.filter((objective) => objective.is_completed === status)
}
</script>

<template>
  <div class="objectives-container">
    <h1 class="title">Objectives</h1>
    <div class="tabs">
      <button
        @click="activeTab = 'notCompleted'"
        :class="{ active: activeTab === 'notCompleted' }"
        class="tab-button"
      >
        Active
      </button>
      <button
        @click="activeTab = 'completed'"
        :class="{ active: activeTab === 'completed' }"
        class="tab-button"
      >
        Completed
      </button>
    </div>

    <div v-if="activeTab === 'notCompleted'" class="tab-content">
      <ul class="objective-list">
        <li v-for="objective in filterObjectives(false)" :key="objective.id" class="objective-item">
          <div class="objective-details">
            <h3 class="objective-title">{{ objective.challenge }}</h3>
            <p class="objective-progress">
              Progress: {{ objective.progress }} / {{ objective.total }}
            </p>
            <p class="objective-reward">Reward: {{ objective.reward }}</p>
          </div>
        </li>
      </ul>
    </div>

    <div v-if="activeTab === 'completed'" class="tab-content">
      <ul class="objective-list">
        <li
          v-for="objective in filterObjectives(true)"
          :key="objective.id"
          class="objective-item completed-objective"
        >
          <div class="objective-details">
            <h3 class="objective-title">{{ objective.challenge }}</h3>
            <p class="objective-reward">Reward: {{ objective.reward }}</p>
            <p class="objective-progress">
              Progress: {{ objective.progress }} / {{ objective.total }}
            </p>
            <p class="objective-status">Status: Completed</p>
          </div>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.objectives-container {
  max-width: 1200px; /* Increased the width */
  margin: 0 auto;
  padding: 24px; /* Increased padding for more space */
  background-color: #1a1a1a;
  color: #00ff00;
  border: 2px solid #00ff00;
  border-radius: 8px;
}

.title {
  font-size: 2.5rem; /* Increased font size for title */
  font-weight: bold;
  margin-bottom: 24px; /* Increased bottom margin */
  text-align: center;
}

.tabs {
  display: flex;
  justify-content: center;
  margin-bottom: 24px; /* Increased bottom margin */
}

.tab-button {
  padding: 10px 20px; /* Adjusted padding for larger buttons */
  background-color: #2a2a2a;
  color: #00ff00;
  border: 1px solid #00ff00;
  border-radius: 4px;
  margin: 0 12px; /* Increased margin between buttons */
  cursor: pointer;
  transition: background-color 0.3s;
}

.tab-button.active {
  background-color: #00ff00;
  color: #000000;
}

.tab-button:hover {
  background-color: #00ff44;
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
  padding: 16px 20px; /* Increased padding for each item */
  margin-bottom: 16px; /* Increased margin between items */
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
  font-size: 1.5rem; /* Increased font size for objective titles */
  font-weight: bold;
  margin-bottom: 8px; /* Adjusted bottom margin */
}

.objective-reward,
.objective-progress,
.objective-status {
  font-size: 1.1rem; /* Slightly increased font size */
  font-weight: normal;
  color: #b2ffb2;
  margin: 4px 0; /* Adjusted margins */
}

.completed-objective .objective-details {
  color: #777777;
}
</style>
