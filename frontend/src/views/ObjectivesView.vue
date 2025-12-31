<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useObjectivesStore } from '@/stores/objectives'
import { useVaultStore } from '@/stores/vault'
import SidePanel from '@/components/common/SidePanel.vue'
import { useSidePanel } from '@/composables/useSidePanel'

const route = useRoute()
const objectivesStore = useObjectivesStore()
const vaultStore = useVaultStore()
const { isCollapsed } = useSidePanel()
const activeTab = ref('notCompleted')

const vaultId = computed(() => route.params.id as string)
const currentVault = computed(() => vaultId.value ? vaultStore.loadedVaults[vaultId.value] : null)

onMounted(() => {
  if (vaultId.value) {
    objectivesStore.fetchObjectives(vaultId.value)
  }
})

const filterObjectives = (status: boolean) => {
  return objectivesStore.objectives.filter((objective) => objective.is_completed === status)
}

const activeObjectives = computed(() => filterObjectives(false))
const completedObjectives = computed(() => filterObjectives(true))
</script>

<template>
  <div class="relative min-h-screen bg-terminalBackground font-mono text-terminalGreen">
    <div class="scanlines"></div>

    <div class="vault-layout">
      <!-- Side Panel -->
      <SidePanel />

      <!-- Main Content Area -->
      <div class="main-content flicker" :class="{ collapsed: isCollapsed }">
        <div class="container mx-auto px-4 py-8">
          <div class="objectives-container">
    <h1 class="title">
      {{ currentVault ? `Vault ${currentVault.number} Objectives` : 'Objectives' }}
    </h1>
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
      <div v-if="activeObjectives.length === 0" class="empty-state">
        <p>No active objectives</p>
      </div>
      <ul v-else class="objective-list">
        <li v-for="objective in activeObjectives" :key="objective.id" class="objective-item">
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
      <div v-if="completedObjectives.length === 0" class="empty-state">
        <p>No completed objectives yet</p>
      </div>
      <ul v-else class="objective-list">
        <li
          v-for="objective in completedObjectives"
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
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.vault-layout {
  display: flex;
  min-height: 100vh;
}

.main-content {
  flex: 1;
  margin-left: 240px; /* Width of expanded side panel */
  transition: margin-left 0.3s ease;
  font-weight: 600; /* Bold font for better readability */
  letter-spacing: 0.025em; /* Slight letter spacing for clarity */
  line-height: 1.6; /* Better line height for readability */
}

.main-content.collapsed {
  margin-left: 64px;
}

/* Enhanced text styles */
.main-content h1,
.main-content h2,
.main-content h3 {
  font-weight: 700;
  text-shadow: 0 0 8px rgba(0, 255, 0, 0.5);
}

.main-content p,
.main-content span,
.main-content div {
  text-shadow: 0 0 2px rgba(0, 255, 0, 0.3);
}

.scanlines {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: linear-gradient(to bottom, rgba(0, 0, 0, 0.1) 50%, transparent 50%);
  background-size: 100% 2px;
  pointer-events: none;
}


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

.empty-state {
  text-align: center;
  padding: 48px 24px;
  color: #666666;
  font-size: 1.25rem;
}
</style>
