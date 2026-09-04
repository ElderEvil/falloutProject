<script setup lang="ts">
import { ref, computed, onMounted, watch, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { storeToRefs } from 'pinia'
import { Icon } from '@iconify/vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useQuestStore } from '@/modules/progression/stores/quest'
import { useSidePanel } from '@/core/composables/useSidePanel'
import { usePolling } from '@/core/composables/usePolling'
import { useToast } from '@/core/composables/useToast'
import SidePanel from '@/core/components/common/SidePanel.vue'
import PageContentRail from '@/core/components/common/PageContentRail.vue'
import PageHeader from '@/core/components/common/PageHeader.vue'
import TerminalLoadingState from '@/core/components/common/TerminalLoadingState.vue'
import ExplorerCard from '../components/ExplorerCard.vue'
import QuestPartyCard from '../components/QuestPartyCard.vue'
import ExplorationEventLog from '@/modules/exploration/components/ExplorationEventLog.vue'
import ExplorationRewardsModal from '../components/ExplorationRewardsModal.vue'
import UCard from '@/core/components/ui/UCard.vue'
import UButton from '@/core/components/ui/UButton.vue'
import { useExplorationStore } from '../stores/exploration'
import type { RewardsSummary } from '../stores/exploration'
import { usePendingReports, removePendingReport } from '../composables/usePendingReports'

const route = useRoute()
const authStore = useAuthStore()
const { isCollapsed } = useSidePanel()
const { filter: dwellerStore } = useDwellerStore()
const explorationStore = useExplorationStore()
const vaultStore = useVaultStore()
const questStore = useQuestStore()
const toast = useToast()

const vaultId = computed(() => route.params.id as string)
const selectedExplorerId = ref<string | null>(null)
const selectedQuestPartyId = ref<string | null>(null)

const { isLoading: explorationLoading, error: explorationError } = storeToRefs(explorationStore)

const showRewardsModal = ref(false)
const completedExplorationRewards = ref<RewardsSummary | null>(null)
const completedDwellerName = ref('')
const activeQueuedReportId = ref<string | null>(null)

const { pendingReports } = usePendingReports(vaultId)

function showNextPendingReport(): void {
  const next = pendingReports.value[0]
  if (next) {
    activeQueuedReportId.value = next.id
    completedExplorationRewards.value = next.rewards
    completedDwellerName.value = next.dwellerName
    showRewardsModal.value = true
  }
}

const loadData = async () => {
  if (!vaultId.value || !authStore.token) return

  try {
    await explorationStore.fetchExplorationsByVault(vaultId.value, authStore.token)
    await dwellerStore.fetchDwellersByVault(vaultId.value, authStore.token)
    await questStore.fetchVaultQuests(vaultId.value)
    await questStore.fetchPartiesForActiveQuests(vaultId.value)

    for (const exploration of activeExplorationsArray.value) {
      await dwellerStore.fetchDwellerDetails(exploration.dweller_id, authStore.token)
    }
  } catch (error) {
    toast.error('Failed to load exploration data')
  }
}

onMounted(async () => {
  await loadData()
  if (vaultId.value && authStore.token) {
    explorationStore.startSseSubscription(vaultId.value, authStore.token)
  }
  if (pendingReports.value.length > 0) {
    showNextPendingReport()
  }
})

onUnmounted(() => {
  explorationStore.stopSseSubscription()
})

watch(
  () => explorationStore.pendingSseRewards,
  (pending) => {
    if (!pending) return
    if (explorationStore.consumeAcknowledgedSseReward(pending.dwellerId)) {
      explorationStore.clearPendingSseRewards()
      return
    }
    activeQueuedReportId.value = null
    const dweller = getDwellerById(pending.dwellerId)
    completedExplorationRewards.value = pending.rewards
    completedDwellerName.value = dweller ? `${dweller.first_name} ${dweller.last_name}` : 'Dweller'
    showRewardsModal.value = true
    explorationStore.clearPendingSseRewards()
  }
)

const pollExplorations = async () => {
  if (!vaultId.value || !authStore.token) return

  try {
    await explorationStore.fetchExplorationsByVault(vaultId.value, authStore.token)
    await questStore.fetchVaultQuests(vaultId.value, { silent: true })
    await questStore.fetchPartiesForActiveQuests(vaultId.value)
  } catch (error) {
    toast.error('Failed to refresh activities')
  }
}

usePolling(pollExplorations, { interval: 15_000, immediate: false })

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
  return questStore.questCategories.active.filter((q) => {
    const party = questStore.questPartyMap[q.id]
    return party && party.length > 0
  })
})

type ExplorationFinishAction = (explorationId: string, token: string) => Promise<{ rewards_summary?: RewardsSummary }>

const finishExploration = async (
  explorationId: string,
  action: ExplorationFinishAction,
  errorMessage: string
) => {
  if (!authStore.token) return

  try {
    const exploration = explorationStore.activeExplorations[explorationId]
    if (!exploration) return

    const dweller = getDwellerById(exploration.dweller_id)
    if (!dweller) return

    const result = await action(explorationId, authStore.token)

    if (result?.rewards_summary) {
      explorationStore.acknowledgeSseReward(dweller.id)
      completedExplorationRewards.value = result.rewards_summary
      completedDwellerName.value = `${dweller.first_name} ${dweller.last_name}`
      showRewardsModal.value = true
    }

    if (vaultId.value) {
      await vaultStore.refreshVault(vaultId.value, authStore.token)
      await dwellerStore.fetchDwellersByVault(vaultId.value, authStore.token)
    }

    if (selectedExplorerId.value === explorationId) selectedExplorerId.value = null
  } catch (_error) {
    toast.error(errorMessage)
  }
}

const handleCompleteExploration = (explorationId: string) =>
  finishExploration(explorationId, explorationStore.completeExploration, 'Failed to complete exploration')

const handleRecallExploration = (explorationId: string) =>
  finishExploration(explorationId, explorationStore.recallDweller, 'Failed to recall dweller')

const closeRewardsModal = () => {
  if (activeQueuedReportId.value) {
    removePendingReport(activeQueuedReportId.value)
    activeQueuedReportId.value = null
    if (pendingReports.value.length > 0) {
      showNextPendingReport()
      return
    }
  }
  showRewardsModal.value = false
  completedExplorationRewards.value = null
  completedDwellerName.value = ''
}
</script>

<template>
  <div class="exploration-layout">
    <SidePanel />

    <div class="exploration-view" :class="{ collapsed: isCollapsed }">
      <PageContentRail>
        <PageHeader
          title="Wasteland Exploration"
          icon="mdi:compass"
          subtitle="Monitor active explorations and quest parties"
        />

        <!-- Main Content -->
        <div class="exploration-content">
        <!-- Loading State -->
        <TerminalLoadingState v-if="explorationLoading" message="Scanning wasteland frequencies..." />

        <!-- Error State -->
        <div v-else-if="explorationError" class="error-state">
          <UCard padding="lg" :bordered="true">
            <div class="error-content">
              <Icon icon="mdi:alert-circle" class="error-icon" />
              <h3 class="error-title">Signal Lost</h3>
              <p class="error-message">{{ explorationError }}</p>
              <UButton variant="secondary" size="md" @click="loadData">
                <Icon icon="mdi:refresh" class="mr-2" />
                Retry Connection
              </UButton>
            </div>
          </UCard>
        </div>

        <!-- Explorer Cards List -->
        <div v-else class="explorers-section">
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

          <div v-else class="activity-groups">
            <section v-if="activeExplorationsArray.length > 0" class="activity-group">
              <div class="activity-heading">
                <div>
                  <span class="activity-kicker">Wasteland</span>
                  <h2>Active explorers</h2>
                </div>
                <span>{{ activeExplorationsArray.length }} deployed</span>
              </div>
              <div class="explorers-grid">
                <ExplorerCard
                  v-for="exploration in activeExplorationsArray"
                  :key="exploration.id"
                  :exploration="exploration"
                  :dweller="getDetailedDweller(exploration.dweller_id) ?? undefined"
                  :selected="selectedExplorerId === exploration.id"
                  @select="selectedExplorerId = exploration.id"
                  @complete="handleCompleteExploration"
                  @recall="handleRecallExploration"
                />
              </div>
            </section>

            <section v-if="activeQuestsWithParty.length > 0" class="activity-group">
              <div class="activity-heading">
                <div>
                  <span class="activity-kicker">Overseer dispatch</span>
                  <h2>Quest parties</h2>
                </div>
                <span>{{ activeQuestsWithParty.length }} in progress</span>
              </div>
              <div class="explorers-grid">
                <QuestPartyCard
                  v-for="quest in activeQuestsWithParty"
                  :key="quest.id"
                  :quest="quest"
                  :party-members="getPartyMembersForQuest(quest.id)"
                  :selected="selectedQuestPartyId === quest.id"
                  @select="selectedQuestPartyId = quest.id"
                />
              </div>
            </section>
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
          <ExplorationEventLog :events="selectedExploration.events" reverse />
        </div>
        </div>
      </PageContentRail>

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
  background: var(--color-terminal-background);
}

.exploration-view {
  flex: 1;
  overflow-y: auto;
  background: var(--color-terminal-background);
  font-family: 'Courier New', monospace;
  margin-left: 240px;
  transition: margin-left 0.3s ease;
}

.exploration-view.collapsed {
  margin-left: 64px;
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

.activity-groups {
  display: grid;
  gap: 2rem;
}

.activity-group {
  display: grid;
  gap: 1rem;
}

.activity-heading {
  align-items: end;
  border-bottom: 1px solid color-mix(in srgb, var(--color-theme-primary) 25%, transparent);
  display: flex;
  justify-content: space-between;
  padding-bottom: 0.75rem;
}

.activity-kicker {
  color: var(--color-theme-accent);
  display: block;
  font-size: 0.7rem;
  letter-spacing: 0.12em;
  margin-bottom: 0.25rem;
  text-transform: uppercase;
}

.activity-heading h2 {
  color: var(--color-theme-primary);
  font-size: 1.2rem;
  font-weight: 700;
}

.activity-heading > span {
  color: var(--color-theme-primary);
  font-size: 0.75rem;
  opacity: 0.7;
}

/* Error State */
.error-state {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem;
}

.error-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
  text-align: center;
}

.error-icon {
  width: 4rem;
  height: 4rem;
  color: var(--color-danger, #ef4444);
  filter: drop-shadow(0 0 10px var(--color-danger, #ef4444));
}

.error-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--color-danger, #ef4444);
  text-shadow: 0 0 6px var(--color-danger, #ef4444);
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.error-message {
  font-size: 0.875rem;
  color: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.7);
  max-width: 400px;
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
