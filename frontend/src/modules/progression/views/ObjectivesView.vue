<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useObjectivesStore } from '@/stores/objectives'
import { useVaultStore } from '@/modules/vault/stores/vault'
import SidePanel from '@/core/components/common/SidePanel.vue'
import { useSidePanel } from '@/core/composables/useSidePanel'
import { Icon } from '@iconify/vue'
import { ObjectiveCard } from '../components'

const route = useRoute()
const objectivesStore = useObjectivesStore()
const vaultStore = useVaultStore()
const { isCollapsed } = useSidePanel()
const activeTab = ref('daily')

const vaultId = computed(() => route.params.id as string)
const currentVault = computed(() => (vaultId.value ? vaultStore.loadedVaults[vaultId.value] : null))

onMounted(() => {
  if (vaultId.value) {
    objectivesStore.fetchObjectives(vaultId.value)
  }
})

const completedObjectives = computed(() =>
  objectivesStore.objectives.filter((objective) => objective.is_completed === true)
)

const dailyObjectives = computed(() =>
  objectivesStore.objectives.filter((obj) => obj.category === 'daily' && !obj.is_completed)
)

const weeklyObjectives = computed(() =>
  objectivesStore.objectives.filter((obj) => obj.category === 'weekly' && !obj.is_completed)
)

const achievementObjectives = computed(() =>
  objectivesStore.objectives.filter((obj) => obj.category === 'achievement' && !obj.is_completed)
)
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
                @click="activeTab = 'daily'"
                :class="{ active: activeTab === 'daily' }"
                class="tab-button"
              >
                <Icon icon="mdi:calendar-today" class="inline mr-2" />
                Daily
              </button>
              <button
                @click="activeTab = 'weekly'"
                :class="{ active: activeTab === 'weekly' }"
                class="tab-button"
              >
                <Icon icon="mdi:calendar-week" class="inline mr-2" />
                Weekly
              </button>
              <button
                @click="activeTab = 'achievement'"
                :class="{ active: activeTab === 'achievement' }"
                class="tab-button"
              >
                <Icon icon="mdi:trophy" class="inline mr-2" />
                Achievement
              </button>
              <button
                @click="activeTab = 'completed'"
                :class="{ active: activeTab === 'completed' }"
                class="tab-button"
              >
                <Icon icon="mdi:check-circle" class="inline mr-2" />
                Completed
              </button>
            </div>

            <div v-if="activeTab === 'daily'" class="tab-content">
              <div v-if="dailyObjectives.length === 0" class="empty-state">
                <p>No daily objectives available</p>
              </div>
              <div v-else class="objective-grid">
                <ObjectiveCard
                  v-for="objective in dailyObjectives"
                  :key="objective.id"
                  :objective="objective"
                />
              </div>
            </div>

            <div v-if="activeTab === 'weekly'" class="tab-content">
              <div v-if="weeklyObjectives.length === 0" class="empty-state">
                <p>No weekly objectives available</p>
              </div>
              <div v-else class="objective-grid">
                <ObjectiveCard
                  v-for="objective in weeklyObjectives"
                  :key="objective.id"
                  :objective="objective"
                />
              </div>
            </div>

            <div v-if="activeTab === 'achievement'" class="tab-content">
              <div v-if="achievementObjectives.length === 0" class="empty-state">
                <p>No achievement objectives available</p>
              </div>
              <div v-else class="objective-grid">
                <ObjectiveCard
                  v-for="objective in achievementObjectives"
                  :key="objective.id"
                  :objective="objective"
                />
              </div>
            </div>

            <div v-if="activeTab === 'completed'" class="tab-content">
              <div v-if="completedObjectives.length === 0" class="empty-state">
                <p>No completed objectives yet</p>
              </div>
              <div v-else class="objective-grid">
                <ObjectiveCard
                  v-for="objective in completedObjectives"
                  :key="objective.id"
                  :objective="objective"
                />
              </div>
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
  text-shadow: 0 0 8px var(--color-theme-glow);
}

.main-content p,
.main-content span,
.main-content div {
  text-shadow: 0 0 2px var(--color-theme-glow);
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
  max-width: 1400px;
  margin: 0 auto;
}

.title {
  font-size: 2.5rem;
  font-weight: bold;
  margin-bottom: 24px;
  text-align: center;
}

.tabs {
  display: flex;
  justify-content: flex-start;
  gap: 0;
  margin-bottom: 24px;
  border-bottom: 2px solid var(--color-theme-glow);
}

.tab-button {
  padding: 10px 24px;
  background-color: transparent;
  color: var(--color-theme-primary);
  border: none;
  border-bottom: 3px solid transparent;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 1rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  opacity: 0.6;
}

.tab-button.active {
  opacity: 1;
  border-bottom-color: var(--color-theme-primary);
  background-color: var(--color-theme-glow);
}

.tab-button:hover:not(.active) {
  opacity: 0.8;
  background-color: rgba(0, 0, 0, 0.2);
}

.objective-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 16px;
}

.objective-list {
  list-style-type: none;
  padding: 0;
  margin: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 16px;
}

.objective-item {
  background: linear-gradient(135deg, #1a1a1a 0%, #2a2a2a 100%);
  border: 2px solid var(--color-theme-primary);
  border-radius: 6px;
  padding: 16px;
  transition: all 0.2s;
  position: relative;
  overflow: hidden;
}

.objective-item::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: var(--color-theme-primary);
  box-shadow: 0 0 8px var(--color-theme-glow);
}

.objective-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px var(--color-theme-glow);
}

.objective-details {
  flex: 1;
}

.objective-title {
  font-size: 1.1rem;
  font-weight: bold;
  margin-bottom: 8px;
  color: var(--color-theme-primary);
}

.objective-reward,
.objective-progress,
.objective-status {
  font-size: 0.9rem;
  font-weight: normal;
  color: var(--color-theme-primary);
  opacity: 0.85;
  margin: 4px 0;
  line-height: 1.5;
}

.completed-objective {
  border-color: #666666;
  opacity: 0.75;
  background: linear-gradient(135deg, #1a1a1a 0%, #252525 100%);
}

.completed-objective::before {
  background: #666666;
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
