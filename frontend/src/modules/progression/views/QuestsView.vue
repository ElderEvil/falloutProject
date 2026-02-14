<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useQuestStore } from '@/stores/quest'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useRoomStore } from '@/stores/room'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import SidePanel from '@/core/components/common/SidePanel.vue'
import { useSidePanel } from '@/core/composables/useSidePanel'
import { Icon } from '@iconify/vue'
import { QuestCard, PartySelectionModal } from '../components'
import type { VaultQuest } from '../models/quest'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'

const route = useRoute()
const questStore = useQuestStore()
const vaultStore = useVaultStore()
const roomStore = useRoomStore()
const authStore = useAuthStore()
const dwellerStore = useDwellerStore()
const { isCollapsed } = useSidePanel()
const activeTab = ref<'active' | 'completed'>('active')
const showAllQuests = ref(false)

// Check if a quest is unlocked (no previous quest or previous is completed)
const isQuestUnlocked = (quest: VaultQuest): boolean => {
  if (!quest.previous_quest_id) return true
  const previousQuest = questStore.vaultQuests.find(q => q.id === quest.previous_quest_id)
  return previousQuest?.is_completed ?? false
}

// Filtered available quests based on toggle
const filteredAvailableQuests = computed(() => {
  if (showAllQuests.value) {
    // Show ALL quests that haven't been started (including locked ones)
    return questStore.vaultQuests.filter(q => !q.started_at && !q.is_completed)
  }
  // Show only visible AND unlocked quests
  return questStore.vaultQuests.filter(q => q.is_visible && !q.started_at && !q.is_completed && isQuestUnlocked(q))
})

// Modal state
const showPartyModal = ref(false)
const selectedQuest = ref<VaultQuest | null>(null)
const questPartyMembers = ref<DwellerShort[]>([])
const questPartyMembersMap = ref<Record<string, DwellerShort[]>>({})

const vaultId = computed(() => route.params.id as string)
const currentVault = computed(() => (vaultId.value ? vaultStore.loadedVaults[vaultId.value] : null))

const hasOverseerOffice = computed(() => {
  return roomStore.rooms.some(
    (room) => room.name.toLowerCase().includes('overseer') || room.category === 'quests'
  )
})

// Computed properties for quest lists
const activeQuests = computed(() => questStore.activeQuests)
const completedQuests = computed(() => questStore.completedQuests)

// Get party members for a specific quest
const getPartyMembersForQuest = async (quest: VaultQuest): Promise<DwellerShort[]> => {
  if (!vaultId.value) return []
  try {
    const party = await questStore.getParty(vaultId.value, quest.id)
    return party
      .map((p) => dwellerStore.dwellers.find((d) => d.id === p.dweller_id))
      .filter((d): d is DwellerShort => d !== undefined)
  } catch {
    return []
  }
}

// Handle opening party selection modal
const handleAssignParty = async (questId: string) => {
  const quest = [...filteredAvailableQuests.value, ...activeQuests.value].find((q) => q.id === questId)
  if (!quest || !vaultId.value) return

  selectedQuest.value = quest

  // Load current party members
  questPartyMembers.value = await getPartyMembersForQuest(quest)

  showPartyModal.value = true
}

// Handle party assignment
const handlePartyAssigned = async (dwellerIds: string[]) => {
  if (!vaultId.value || !selectedQuest.value) {
    return
  }

  try {
    await questStore.assignParty(vaultId.value, selectedQuest.value.id, dwellerIds)

    // Refresh quests to get updated state
    await questStore.fetchVaultQuests(vaultId.value)

    // Fetch party for this specific quest and update map
    const party = await questStore.getParty(vaultId.value, selectedQuest.value.id)
    const mappedParty = party
      .map((p) => dwellerStore.dwellers.find((d) => d.id === p.dweller_id))
      .filter((d): d is DwellerShort => d !== undefined)

    questPartyMembersMap.value[selectedQuest.value.id] = mappedParty

    // Close the modal after successful assignment
    showPartyModal.value = false
    selectedQuest.value = null
    questPartyMembers.value = []
  } catch {
    // Error is already handled in the store (toast notification)
    // Just prevent further execution
  }
}

// Handle starting the quest after party assignment
const handleStartQuestAfterAssign = async () => {
  if (!vaultId.value || !selectedQuest.value) return

  await questStore.startQuest(vaultId.value, selectedQuest.value.id)

  showPartyModal.value = false
  selectedQuest.value = null
  questPartyMembers.value = []
}

// Original handlers (for backwards compatibility)
const handleStartQuest = async (questId: string) => {
  if (!vaultId.value) {
    return
  }
  await questStore.startQuest(vaultId.value, questId)
}

const handleCompleteQuest = async (questId: string) => {
  if (!vaultId.value) return
  await questStore.completeQuest(vaultId.value, questId)
}

// Fetch quests on mount
onMounted(async () => {
  const token = authStore.token || localStorage.getItem('token')?.replace(/^"|"$/g, '')

  if (vaultId.value && token) {
    await roomStore.fetchRooms(vaultId.value, token)
    await dwellerStore.fetchDwellersByVault(vaultId.value, token)

    if (hasOverseerOffice.value) {
      // Fetch all quests so we can filter client-side (including locked ones)
      await questStore.fetchVaultQuests(vaultId.value)
      await questStore.fetchAllQuests()
    }
  }
})
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
          <!-- Locked State -->
          <div v-if="!hasOverseerOffice" class="locked-container">
            <div class="locked-icon">
              <Icon icon="mdi:lock" class="text-9xl opacity-50" />
            </div>
            <h1 class="locked-title">OVERSEER'S OFFICE REQUIRED</h1>
            <p class="locked-description">
              Build an <strong>Overseer's Office</strong> to unlock the quest system and access
              missions for your vault.
            </p>
            <div class="locked-hint">
              <Icon icon="mdi:information" class="inline mr-2" />
              Quests provide special challenges and valuable rewards
            </div>
          </div>

          <!-- Quests View -->
          <div v-else class="quests-container">
            <h1 class="title">
              {{ currentVault ? `Vault ${currentVault.number} Quests` : 'Quests' }}
            </h1>

            <!-- Tabs -->
            <div class="tabs">
              <button
                @click="activeTab = 'active'"
                :class="{ active: activeTab === 'active' }"
                class="tab-button"
              >
                <Icon icon="mdi:play-circle" class="inline mr-2" />
                Active & Available
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

            <!-- Active & Available Quests -->
            <div v-if="activeTab === 'active'" class="tab-content">
              <!-- Active Quests Section -->
              <div v-if="activeQuests.length > 0" class="quest-section">
                <h2 class="section-title">
                  <Icon icon="mdi:progress-check" class="inline mr-2" />
                  ACTIVE QUESTS
                </h2>
                <div class="quest-grid">
                  <QuestCard
                    v-for="quest in activeQuests"
                    :key="quest.id"
                    :quest="quest"
                    :vault-id="vaultId"
                    status="active"
                    :party-members="questPartyMembersMap[quest.id] || []"
                    @complete="handleCompleteQuest"
                    @assign-party="handleAssignParty"
                  />
                </div>
              </div>

              <!-- Available Quests Section -->
              <div v-if="filteredAvailableQuests.length > 0" class="quest-section">
                <div class="section-header">
                  <h2 class="section-title">
                    <Icon icon="mdi:book-open-page-variant" class="inline mr-2" />
                    AVAILABLE QUESTS
                    <span v-if="showAllQuests" class="section-badge">(Showing All)</span>
                  </h2>
                  <label class="toggle-label">
                    <input
                      v-model="showAllQuests"
                      type="checkbox"
                      class="toggle-input"
                    />
                    <span class="toggle-text">Show All</span>
                  </label>
                </div>
                <div class="quest-grid">
                  <QuestCard
                    v-for="quest in filteredAvailableQuests"
                    :key="quest.id"
                    :quest="quest"
                    :vault-id="vaultId"
                    :status="isQuestUnlocked(quest) ? 'available' : 'locked'"
                    :is-locked="!isQuestUnlocked(quest)"
                    :party-members="questPartyMembersMap[quest.id] || []"
                    @start="handleStartQuest"
                    @assign-party="handleAssignParty"
                  />
                </div>
              </div>

              <!-- Empty State -->
              <div
                v-if="activeQuests.length === 0 && filteredAvailableQuests.length === 0"
                class="empty-state"
              >
                <Icon icon="mdi:inbox" class="text-8xl mb-6 opacity-30" />
                <p v-if="showAllQuests">No quests available at the moment</p>
                <p v-else>No unlocked quests available. Complete previous quests to unlock more.</p>
              </div>
            </div>

            <!-- Completed Quests -->
            <div v-if="activeTab === 'completed'" class="tab-content">
              <div v-if="completedQuests.length === 0" class="empty-state">
                <Icon icon="mdi:checkbox-marked-circle-outline" class="text-8xl mb-6 opacity-30" />
                <p>No completed quests yet</p>
              </div>

              <div v-else class="quest-grid">
                <QuestCard
                  v-for="quest in completedQuests"
                  :key="quest.id"
                  :quest="quest"
                  :vault-id="vaultId"
                  status="completed"
                />
              </div>
            </div>
          </div>

          <!-- Party Selection Modal -->
          <PartySelectionModal
            v-model="showPartyModal"
            :quest="selectedQuest"
            :vault-id="vaultId"
            :dwellers="dwellerStore.dwellers"
            :current-party="questPartyMembers"
            @assign="handlePartyAssigned"
            @start="handleStartQuestAfterAssign"
          />
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
  margin-left: 240px;
  transition: margin-left 0.3s ease;
  font-weight: 600;
  letter-spacing: 0.025em;
  line-height: 1.6;
}

.main-content.collapsed {
  margin-left: 64px;
}

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

/* Locked State */
.locked-container {
  max-width: 800px;
  margin: 80px auto;
  padding: 60px 40px;
  background-color: #1a1a1a;
  border: 3px solid var(--color-theme-primary);
  border-radius: 12px;
  text-align: center;
  box-shadow: 0 0 30px var(--color-theme-glow);
}

.locked-icon {
  margin-bottom: 32px;
  color: var(--color-theme-primary);
  opacity: 0.5;
}

.locked-title {
  font-size: 3rem;
  font-weight: bold;
  margin-bottom: 24px;
  color: var(--color-theme-primary);
  letter-spacing: 0.1em;
}

.locked-description {
  font-size: 1.3rem;
  color: var(--color-theme-primary);
  opacity: 0.8;
  line-height: 1.8;
  margin-bottom: 32px;
}

.locked-hint {
  padding: 16px 24px;
  background-color: rgba(0, 0, 0, 0.4);
  border-left: 4px solid var(--color-theme-accent);
  font-size: 1.1rem;
  color: var(--color-theme-accent);
}

/* Quests Container */
.quests-container {
  max-width: 1400px;
  margin: 0 auto;
}

.title {
  font-size: 2.5rem;
  font-weight: bold;
  margin-bottom: 24px;
  text-align: center;
}

/* Tabs */
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

/* Section Title */
.quest-section {
  margin-bottom: 32px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 2px solid var(--color-theme-glow);
}

.section-title {
  font-size: 1.3rem;
  font-weight: bold;
  color: var(--color-theme-primary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 0;
  border-bottom: none;
  padding-bottom: 0;
}

.section-badge {
  font-size: 0.75rem;
  font-weight: normal;
  color: var(--color-theme-accent);
  text-transform: none;
  letter-spacing: normal;
}

.toggle-label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 0.9rem;
  color: var(--color-theme-primary);
}

.toggle-input {
  appearance: none;
  width: 40px;
  height: 20px;
  background: #333;
  border-radius: 10px;
  position: relative;
  cursor: pointer;
  border: 2px solid var(--color-theme-primary);
}

.toggle-input:checked {
  background: var(--color-theme-primary);
}

.toggle-input::after {
  content: '';
  position: absolute;
  width: 14px;
  height: 14px;
  background: #fff;
  border-radius: 50%;
  top: 1px;
  left: 2px;
  transition: transform 0.2s;
}

.toggle-input:checked::after {
  transform: translateX(20px);
}

.toggle-text {
  user-select: none;
}

/* Quest Grid */
.quest-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 16px;
}

/* Quest Card */
.quest-card {
  background: linear-gradient(135deg, #1a1a1a 0%, #2a2a2a 100%);
  border: 2px solid var(--color-theme-primary);
  border-radius: 6px;
  padding: 16px;
  transition: all 0.2s;
  position: relative;
  overflow: hidden;
}

.quest-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: var(--color-theme-primary);
  box-shadow: 0 0 8px var(--color-theme-glow);
}

.quest-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px var(--color-theme-glow);
}

.active-quest {
  border-color: var(--color-theme-accent);
  background: linear-gradient(135deg, #1a1a1a 0%, #2a2a2a 100%);
}

.active-quest::before {
  background: var(--color-theme-accent);
}

.available-quest {
  border-color: var(--color-theme-primary);
}

.completed-quest {
  border-color: #666666;
  opacity: 0.75;
  background: linear-gradient(135deg, #1a1a1a 0%, #252525 100%);
}

.completed-quest::before {
  background: #666666;
}

/* Quest Header */
.quest-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
  gap: 12px;
}

.quest-title {
  font-size: 1.1rem;
  font-weight: bold;
  color: var(--color-theme-primary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  flex: 1;
}

.quest-badge {
  padding: 6px 12px;
  border-radius: 4px;
  font-size: 0.8rem;
  font-weight: bold;
  letter-spacing: 0.1em;
  white-space: nowrap;
  flex-shrink: 0;
}

.active-badge {
  background-color: var(--color-theme-accent);
  color: #000000;
  box-shadow: 0 0 10px var(--color-theme-accent);
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
}

.available-badge {
  background-color: var(--color-theme-primary);
  color: #000000;
}

.completed-badge {
  background-color: #666666;
  color: #ffffff;
}

/* Quest Description */
.quest-description {
  font-size: 0.9rem;
  color: var(--color-theme-primary);
  opacity: 0.85;
  margin-bottom: 12px;
  line-height: 1.5;
}

.quest-section-divider {
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--color-theme-primary), transparent);
  margin: 12px 0;
  opacity: 0.3;
}

/* Quest Details */
.quest-details {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}

.detail-item {
  background-color: rgba(0, 0, 0, 0.3);
  padding: 8px 12px;
  border-left: 2px solid var(--color-theme-primary);
  border-radius: 3px;
}

.detail-label {
  font-size: 0.75rem;
  font-weight: bold;
  color: var(--color-theme-accent);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 4px;
}

.detail-value {
  font-size: 0.9rem;
  color: var(--color-theme-primary);
}

.reward-text {
  font-weight: bold;
  color: var(--color-theme-accent);
}

/* Action Buttons */
.quest-action-btn {
  width: 100%;
  padding: 10px 16px;
  border: 2px solid var(--color-theme-primary);
  border-radius: 4px;
  font-weight: bold;
  font-size: 0.9rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  cursor: pointer;
  transition: all 0.2s;
  font-family: 'Courier New', monospace;
}

.complete-btn {
  background-color: var(--color-theme-accent);
  color: #000000;
  border-color: var(--color-theme-accent);
}

.complete-btn:hover {
  background-color: var(--color-theme-primary);
  box-shadow: 0 0 15px var(--color-theme-glow);
  transform: translateY(-1px);
}

.start-btn {
  background-color: transparent;
  color: var(--color-theme-primary);
}

.start-btn:hover {
  background-color: var(--color-theme-primary);
  color: #000000;
  box-shadow: 0 0 20px var(--color-theme-glow);
  transform: translateY(-2px);
}

/* Completion Stamp */
.completion-stamp {
  text-align: center;
  padding: 12px;
  background-color: rgba(0, 0, 0, 0.5);
  border: 2px dashed #666666;
  border-radius: 4px;
  color: #666666;
  font-weight: bold;
  font-size: 1.1rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

/* Empty State */
.empty-state {
  text-align: center;
  padding: 80px 24px;
  color: var(--color-theme-primary);
  opacity: 0.5;
}

.empty-state p {
  font-size: 1.5rem;
}

</style>
