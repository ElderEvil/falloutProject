<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerStore } from '@/stores/dweller'
import { useExplorationStore } from '../stores/exploration'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useQuestStore } from '@/modules/progression/stores/quest'
import { useSidePanel } from '@/core/composables/useSidePanel'
import { Icon } from '@iconify/vue'
import SidePanel from '@/core/components/common/SidePanel.vue'
import ExplorerCard from '../components/ExplorerCard.vue'
import QuestPartyCard from '../components/QuestPartyCard.vue'
import EventTimeline from '../components/EventTimeline.vue'
import ExplorationRewardsModal from '../components/ExplorationRewardsModal.vue'
import type { RewardsSummary } from '../stores/exploration'

const route = useRoute()
const authStore = useAuthStore()
const { isCollapsed } = useSidePanel()
const dwellerStore = useDwellerStore()
const explorationStore = useExplorationStore()
const vaultStore = useVaultStore()
const questStore = useQuestStore()

const vaultId = computed(() => route.params.id as string)
const selectedExplorerId = ref<string | null>(null)
const selectedQuestPartyId = ref<string | null>(null)

// Rewards modal state
const showRewardsModal = ref(false)
const completedExplorationRewards = ref<RewardsSummary | null>(null)
const completedDwellerName = ref('')

// Fetch explorations on mount
onMounted(async () => {
  if (vaultId.value && authStore.token) {
    try {
      await explorationStore.fetchExplorationsByVault(vaultId.value, authStore.token)
      await dwellerStore.fetchDwellersByVault(vaultId.value, authStore.token)
      await questStore.fetchVaultQuests(vaultId.value)
      await questStore.fetchPartiesForActiveQuests(vaultId.value)

      // Fetch full dweller data for explorers (includes weapon/outfit)
      for (const exploration of activeExplorationsArray.value) {
        await dwellerStore.fetchDwellerDetails(exploration.dweller_id, authStore.token)
      }
    } catch (error) {
      console.error('Failed to load exploration data:', error)
    }
  }
})

// Poll for updates every 15 seconds
let pollInterval: ReturnType<typeof setInterval> | null = null
onMounted(() => {
  pollInterval = setInterval(async () => {
    if (vaultId.value && authStore.token) {
      try {
        await explorationStore.fetchExplorationsByVault(vaultId.value, authStore.token)
      } catch (error) {
        console.error('Failed to poll explorations:', error)
      }
    }
  }, 15000)
})

onUnmounted(() => {
  if (pollInterval) {
    clearInterval(pollInterval)
  }
})

const activeExplorationsArray = computed(() => {
  return Object.values(explorationStore.activeExplorations)
})

const selectedExploration = computed(() => {
  if (!selectedExplorerId.value) return null
  return explorationStore.activeExplorations[selectedExplorerId.value]
})

const getDwellerById = (dwellerId: string) => {
  return dwellerStore.dwellers.find((d) => d.id === dwellerId)
}

const getDetailedDweller = (dwellerId: string) => {
  return dwellerStore.detailedDwellers[dwellerId] || null
}

const getPartyMembersForQuest = (questId: string) => {
  const party = questStore.questPartyMap[questId]
  if (!party) return []
  return party
    .map((p) => dwellerStore.dwellers.find((d) => d.id === p.dweller_id))
    .filter((d): d is NonNullable<typeof d> => d !== undefined)
}

const activeQuestsWithParty = computed(() => {
  return questStore.activeQuests.filter((q) => {
    const party = questStore.questPartyMap[q.id]
    return party && party.length > 0
  })
})

const handleCompleteQuest = async (questId: string) => {
  if (!vaultId.value || !authStore.token) return

  try {
    await questStore.completeQuest(vaultId.value, questId)
    await questStore.fetchVaultQuests(vaultId.value)
    await questStore.fetchPartiesForActiveQuests(vaultId.value)
    if (selectedQuestPartyId.value === questId) {
      selectedQuestPartyId.value = null
    }
  } catch (error) {
    console.error('Failed to complete quest:', error)
  }
}

const handleCompleteExploration = async (explorationId: string) => {
  if (!authStore.token) return

  try {
    const exploration = explorationStore.activeExplorations[explorationId]
    if (!exploration) return

    const dweller = getDwellerById(exploration.dweller_id)
    if (!dweller) return

    const result = await explorationStore.completeExploration(explorationId, authStore.token)

    // Show rewards modal
    if (result?.rewards_summary) {
      completedExplorationRewards.value = result.rewards_summary
      completedDwellerName.value = `${dweller.first_name} ${dweller.last_name}`
      showRewardsModal.value = true
    }

    // Refresh data
    if (vaultId.value) {
      await vaultStore.refreshVault(vaultId.value, authStore.token)
      await dwellerStore.fetchDwellersByVault(vaultId.value, authStore.token)
    }

    // Clear selection if completed explorer was selected
    if (selectedExplorerId.value === explorationId) {
      selectedExplorerId.value = null
    }
  } catch (error) {
    console.error('Failed to complete exploration:', error)
  }
}

const handleRecallExploration = async (explorationId: string) => {
  if (!authStore.token) return

  try {
    const exploration = explorationStore.activeExplorations[explorationId]
    if (!exploration) return

    const dweller = getDwellerById(exploration.dweller_id)
    if (!dweller) return

    const result = await explorationStore.recallDweller(explorationId, authStore.token)

    // Show rewards modal
    if (result?.rewards_summary) {
      completedExplorationRewards.value = result.rewards_summary
      completedDwellerName.value = `${dweller.first_name} ${dweller.last_name}`
      showRewardsModal.value = true
    }

    // Refresh data
    if (vaultId.value) {
      await vaultStore.refreshVault(vaultId.value, authStore.token)
      await dwellerStore.fetchDwellersByVault(vaultId.value, authStore.token)
    }

    // Clear selection if recalled explorer was selected
    if (selectedExplorerId.value === explorationId) {
      selectedExplorerId.value = null
    }
  } catch (error) {
    console.error('Failed to recall dweller:', error)
  }
}

const closeRewardsModal = () => {
  showRewardsModal.value = false
  completedExplorationRewards.value = null
  completedDwellerName.value = ''
}
</script>

<template>
  <div class="exploration-layout">
    <SidePanel />

    <div class="exploration-view" :class="{ collapsed: isCollapsed }">
      <!-- Header -->
      <div class="view-header">
        <div class="header-content">
          <Icon icon="mdi:compass" class="header-icon" />
          <div>
            <h1 class="header-title">Wasteland Exploration</h1>
            <p class="header-subtitle">Monitor active explorations and quest parties</p>
          </div>
        </div>
        <div class="header-stats">
          <div class="stat-badge">
            <Icon icon="mdi:account-search" class="stat-icon" />
            <span class="stat-value">{{ activeExplorationsArray.length }}</span>
            <span class="stat-label">Explorations</span>
          </div>
          <div class="stat-badge">
            <Icon icon="mdi:sword-cross" class="stat-icon" />
            <span class="stat-value">{{ activeQuestsWithParty.length }}</span>
            <span class="stat-label">Quests</span>
          </div>
        </div>
      </div>

      <!-- Main Content -->
      <div class="exploration-content">
        <!-- Explorer Cards List -->
        <div class="explorers-section">
          <div
            v-if="activeExplorationsArray.length === 0 && activeQuestsWithParty.length === 0"
            class="empty-state"
          >
            <Icon icon="mdi:compass-off" class="empty-icon" />
            <h3 class="empty-title">No Active Activities</h3>
            <p class="empty-text">
              Send dwellers to the wasteland or assign quest parties to see them here.
            </p>
          </div>

          <div v-else class="explorers-grid">
            <ExplorerCard
              v-for="exploration in activeExplorationsArray"
              :key="exploration.id"
              :exploration="exploration"
              :dweller="getDetailedDweller(exploration.dweller_id)"
              :selected="selectedExplorerId === exploration.id"
              @select="selectedExplorerId = exploration.id"
              @complete="handleCompleteExploration"
              @recall="handleRecallExploration"
            />
            <QuestPartyCard
              v-for="quest in activeQuestsWithParty"
              :key="quest.id"
              :quest="quest"
              :party-members="getPartyMembersForQuest(quest.id)"
              :selected="selectedQuestPartyId === quest.id"
              @select="selectedQuestPartyId = quest.id"
              @complete="handleCompleteQuest"
            />
          </div>
        </div>

        <!-- Event Timeline Sidebar -->
        <div v-if="selectedExploration" class="timeline-section">
          <div class="timeline-header">
            <div class="timeline-title">
              <Icon icon="mdi:timeline-text" class="mr-2" />
              Event Log
            </div>
            <button @click="selectedExplorerId = null" class="close-timeline-btn" title="Close">
              <Icon icon="mdi:close" />
            </button>
          </div>
          <EventTimeline
            :exploration="selectedExploration"
            :dweller="getDetailedDweller(selectedExploration.dweller_id)"
          />
        </div>
      </div>

      <!-- Rewards Modal -->
      <ExplorationRewardsModal
        :show="showRewardsModal"
        :rewards="completedExplorationRewards"
        :dweller-name="completedDwellerName"
        @close="closeRewardsModal"
      />
    </div>
  </div>
</template>

<style scoped>
.exploration-layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
  background: #000;
}

.exploration-view {
  flex: 1;
  padding: 2rem;
  overflow-y: auto;
  background: #000;
  font-family: 'Courier New', monospace;
  margin-left: 240px;
  transition: margin-left 0.3s ease;
}

.exploration-view.collapsed {
  margin-left: 64px;
}

.view-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 2rem;
  padding-bottom: 1.5rem;
  border-bottom: 2px solid var(--color-theme-primary);
  box-shadow: 0 2px 0 0 var(--color-theme-glow);
}

.header-content {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.header-icon {
  width: 3rem;
  height: 3rem;
  color: var(--color-theme-primary);
  filter: drop-shadow(0 0 8px var(--color-theme-glow));
}

.header-title {
  font-size: 2rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 10px var(--color-theme-glow);
  margin-bottom: 0.25rem;
}

.header-subtitle {
  font-size: 0.875rem;
  color: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.7);
}

.header-stats {
  display: flex;
  gap: 1rem;
}

.stat-badge {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
  padding: 0.75rem 1.5rem;
  background: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.1);
  border: 2px solid var(--color-theme-primary);
  border-radius: 8px;
}

.stat-icon {
  width: 1.5rem;
  height: 1.5rem;
  color: var(--color-theme-primary);
}

.stat-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 8px var(--color-theme-glow);
}

.stat-label {
  font-size: 0.75rem;
  color: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.7);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.exploration-content {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1.5rem;
  position: relative;
}

.exploration-content:has(.timeline-section) {
  grid-template-columns: 1fr 400px;
}

.explorers-section {
  min-height: 400px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem 2rem;
  background: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.03);
  border: 2px dashed rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.3);
  border-radius: 12px;
  gap: 1rem;
}

.empty-icon {
  width: 5rem;
  height: 5rem;
  color: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.3);
}

.empty-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 6px var(--color-theme-glow);
}

.empty-text {
  font-size: 0.875rem;
  color: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.6);
  text-align: center;
  max-width: 500px;
}

.explorers-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 1.5rem;
}

.timeline-section {
  position: sticky;
  top: 1rem;
  height: fit-content;
  max-height: calc(100vh - 200px);
  background: rgba(0, 0, 0, 0.95);
  border: 2px solid var(--color-theme-primary);
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 0 20px var(--color-theme-glow);
}

.timeline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  background: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.1);
  border-bottom: 2px solid var(--color-theme-primary);
}

.timeline-title {
  display: flex;
  align-items: center;
  font-size: 1rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 6px var(--color-theme-glow);
}

.close-timeline-btn {
  background: transparent;
  border: 2px solid rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.5);
  color: var(--color-theme-primary);
  padding: 0.25rem;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  font-size: 1.25rem;
}

.close-timeline-btn:hover {
  background: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.2);
  border-color: var(--color-theme-primary);
}

/* Responsive */
@media (max-width: 1200px) {
  .exploration-content:has(.timeline-section) {
    grid-template-columns: 1fr;
  }

  .timeline-section {
    position: relative;
    top: 0;
    max-height: 600px;
  }
}

@media (max-width: 768px) {
  .exploration-view {
    padding: 1rem;
  }

  .view-header {
    flex-direction: column;
    gap: 1rem;
  }

  .explorers-grid {
    grid-template-columns: 1fr;
  }
}
</style>
