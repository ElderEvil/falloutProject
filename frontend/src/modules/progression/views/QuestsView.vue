<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useLocalStorage } from '@vueuse/core'
import { useQuestStore } from '@/modules/progression/stores/quest'
import { useRoomStore } from '@/modules/rooms/stores/room'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import SidePanel from '@/core/components/common/SidePanel.vue'
import PageContentRail from '@/core/components/common/PageContentRail.vue'
import { useSidePanel } from '@/core/composables/useSidePanel'
import { useToast } from '@/core/composables/useToast'
import { usePolling } from '@/core/composables/usePolling'
import PageHeader from '@/core/components/common/PageHeader.vue'
import { Icon } from '@iconify/vue'
import { Tabs, TabsList, TabsTrigger } from '@/core/components/ui/tabs'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/core/components/ui/select'
import { QuestCard, PartySelectionModal } from '../components'
import QuestRewardsModal from '../components/QuestRewardsModal.vue'
import QuestDetailModal from '../components/QuestDetailModal.vue'
import type { QuestAvailableSortBy, VaultQuest } from '../models/quest'
import {
  compareQuestsByAvailableSort,
  isQuestReturning,
  isStateQuestCategory,
} from '../models/quest'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'

const route = useRoute()
const router = useRouter()
const questStore = useQuestStore()
const roomStore = useRoomStore()
const authStore = useAuthStore()
const { filter: dwellerStore } = useDwellerStore()
const { isCollapsed } = useSidePanel()
const toast = useToast()
const activeTab = ref('active')
const showAllQuests = ref(false)
const questTabs = [
  { key: 'active', label: 'Active', icon: 'mdi:play-circle' },
  { key: 'available', label: 'Available', icon: 'mdi:book-open-page-variant' },
  { key: 'completed', label: 'Completed', icon: 'mdi:check-circle' },
]

// Filtered available quests based on toggle
const filteredAvailableQuests = computed(() => {
  const isAvailableQuest = (q: VaultQuest) => !q.started_at && !q.is_completed

  if (showAllQuests.value) {
    return questStore.vaultQuests.filter(isAvailableQuest)
  }
  return questStore.vaultQuests.filter((q) => q.is_visible && isAvailableQuest(q) && !q.is_locked)
})

const availableSort = useLocalStorage<QuestAvailableSortBy>('questAvailableSort', 'level')
const availableSortOptions: { value: QuestAvailableSortBy; label: string }[] = [
  { value: 'level', label: 'Required Level' },
  { value: 'duration', label: 'Duration' },
  { value: 'type', label: 'Type' },
]

const onAvailableSortChange = (value: unknown) => {
  availableSort.value = String(value) as QuestAvailableSortBy
}

const sortedAvailableQuests = computed(() =>
  [...filteredAvailableQuests.value].sort((a, b) =>
    compareQuestsByAvailableSort(a, b, availableSort.value)
  )
)

// Modal state
const showPartyModal = ref(false)
const selectedQuest = ref<VaultQuest | null>(null)
const questPartyMembers = ref<DwellerShort[]>([])
const questPartyMembersMap = ref<Record<string, DwellerShort[]>>({})
const showClaimModal = ref(false)
const claimQuest = ref<VaultQuest | null>(null)

const vaultId = computed(() => route.params.id as string)

// Deep-linkable quest detail modal: `?quest=<id>` opens it while the list stays mounted.
const selectedQuestId = computed(() => (route.query.quest as string) || '')
const claimQuestId = computed(() => (route.query.claimQuest as string) || '')

const openQuest = (questId: string) => {
  if (!vaultId.value) return
  void router.push({ query: { ...route.query, quest: questId } })
}

const closeQuest = () => {
  void router.replace({ query: { ...route.query, quest: undefined } })
}

// The backend owns quest locking; the full-screen gate shows while the Overseer's Office is missing.
const officeLocked = computed(() =>
  questStore.vaultQuests.some((quest) => quest.lock_reason === "Requires Overseer's Office")
)

// Computed properties for quest lists
const activeQuests = computed(() => questStore.questCategories.active)
const returningQuests = computed(() => questStore.questCategories.returning)
const readyToClaimQuests = computed(() => questStore.questCategories.readyToClaim)
const completedQuests = computed(() => questStore.questCategories.completed)
// Travelling parties stay visible on the active tab and keep the poll alive.
const travellingOrActiveQuests = computed(() => [...activeQuests.value, ...returningQuests.value])

const refreshActiveQuests = async () => {
  if (!vaultId.value || travellingOrActiveQuests.value.length === 0) return
  await questStore.fetchVaultQuests(vaultId.value, { silent: true })
  await loadPartyMembers()
}

const { pause: pauseQuestPolling, resume: resumeQuestPolling } = usePolling(refreshActiveQuests, {
  interval: 30_000,
  immediate: false,
})

watch(
  travellingOrActiveQuests,
  (quests) => {
    if (quests.length > 0) {
      resumeQuestPolling()
    } else {
      pauseQuestPolling()
    }
  },
  { immediate: true }
)

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

const loadPartyMembers = async () => {
  if (!vaultId.value) return
  await questStore.fetchPartiesForActiveQuests(vaultId.value)
  const map: Record<string, DwellerShort[]> = {}
  for (const [questId, members] of Object.entries(questStore.questPartyMap)) {
    map[questId] = members
      .map((m) => dwellerStore.dwellers.find((d) => d.id === m.dweller_id))
      .filter((d): d is DwellerShort => d !== undefined)
  }
  questPartyMembersMap.value = map
}

// Handle opening party selection modal
const handleAssignParty = async (questId: string) => {
  const quest = questStore.vaultQuests.find((q) => q.id === questId)
  if (!quest || !vaultId.value) return

  selectedQuest.value = quest

  // Load current party members
  questPartyMembers.value = await getPartyMembersForQuest(quest)

  showPartyModal.value = true
}

// Handle party assignment + quest start (combined in one click)
const handleAssignAndStart = async (dwellerIds: string[]) => {
  if (!vaultId.value || !selectedQuest.value) {
    return
  }

  try {
    await questStore.assignParty(vaultId.value, selectedQuest.value.id, dwellerIds)
  } catch (err) {
    const errorMessage = err instanceof Error ? err.message : 'Failed to assign party'
    toast.error(errorMessage)
    return
  }

  try {
    await questStore.startQuest(vaultId.value, selectedQuest.value.id)
  } catch (err) {
    const errorMessage = err instanceof Error ? err.message : 'Failed to start quest'
    toast.error(errorMessage)
    await questStore.fetchVaultQuests(vaultId.value)
    showPartyModal.value = false
    selectedQuest.value = null
    questPartyMembers.value = []
    return
  }

  await questStore.fetchVaultQuests(vaultId.value)
  await loadPartyMembers()

  showPartyModal.value = false
  selectedQuest.value = null
  questPartyMembers.value = []
  closeQuest()
}

const isStateQuest = (quest: VaultQuest) => isStateQuestCategory(quest.quest_category)

// State quests settle from vault progress and start with no party; others must assign one first.
const isStarting = ref(false)
const handleStartFromModal = async (questId: string) => {
  if (isStarting.value) return
  const quest = questStore.vaultQuests.find((q) => q.id === questId)
  if (!quest || !vaultId.value) return

  if (isStateQuest(quest)) {
    isStarting.value = true
    try {
      await questStore.startQuest(vaultId.value, quest.id)
    } finally {
      isStarting.value = false
    }
    // A chain click during the await can select a different quest; only close that one's modal.
    if (selectedQuestId.value === questId) closeQuest()
    return
  }

  await handleAssignParty(questId)
}

const handleClaimRewards = (questId: string) => {
  claimQuest.value = readyToClaimQuests.value.find((quest) => quest.id === questId) ?? null
  showClaimModal.value = claimQuest.value !== null
}

watch(
  [claimQuestId, readyToClaimQuests],
  ([questId]) => {
    if (questId) handleClaimRewards(questId)
  },
  { immediate: true }
)

const closeClaimModal = () => {
  showClaimModal.value = false
  claimQuest.value = null
  if (claimQuestId.value) {
    void router.replace({ query: { ...route.query, claimQuest: undefined } })
  }
}

const isClaiming = ref(false)
const confirmClaimRewards = async () => {
  const claim = claimQuest.value
  if (!vaultId.value || !claim || isClaiming.value) return
  // The store claims and announces the granted rewards via toast; Confirm & Claim
  // is the final screen — the modal closes once delivery is confirmed.
  isClaiming.value = true
  try {
    await questStore.claimQuestRewards(vaultId.value, claim.id)
    // Cancelling can open another claim dialog while this one is pending.
    if (claimQuest.value?.id === claim.id) closeClaimModal()
  } finally {
    isClaiming.value = false
  }
}

// Fetch quests on mount
onMounted(async () => {
  const token = authStore.token || localStorage.getItem('token')?.replace(/^"|"$/g, '')

  if (vaultId.value && token) {
    await roomStore.fetchRooms(vaultId.value, token)
    await dwellerStore.fetchDwellersByVault(vaultId.value, token)

    // Fetch all quests so we can filter client-side (including locked ones)
    await questStore.fetchVaultQuests(vaultId.value)
    await questStore.fetchAllQuests()
    await loadPartyMembers()
  }
})
</script>

<template>
  <div class="relative min-h-screen bg-terminal-background font-mono text-terminal-green">
    <div class="vault-layout">
      <!-- Side Panel -->
      <SidePanel />

      <!-- Main Content Area -->
      <div class="main-content flicker" :class="{ collapsed: isCollapsed }">
        <PageContentRail>
          <!-- Locked State -->
          <div v-if="officeLocked" class="locked-container">
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
            <PageHeader
              title="Quests"
              icon="mdi:book-open-page-variant"
              subtitle="Deploy teams, track missions & collect rewards."
            />

            <Tabs :model-value="activeTab" @update:model-value="activeTab = String($event)">
              <TabsList>
                <TabsTrigger v-for="tab in questTabs" :key="tab.key" :value="tab.key">
                  <Icon v-if="tab.icon" :icon="tab.icon" class="mr-2 inline" :ariaHidden="true" />
                  {{ tab.label }}
                </TabsTrigger>
              </TabsList>
              <!-- Active Quests -->
              <div v-if="activeTab === 'active'" class="tab-content">
                <div v-if="readyToClaimQuests.length > 0" class="quest-section">
                  <h2 class="section-title">
                    <Icon icon="mdi:treasure-chest" class="inline mr-2" />
                    REWARDS READY TO CLAIM
                  </h2>
                  <div class="quest-grid">
                    <QuestCard
                      v-for="quest in readyToClaimQuests"
                      :key="quest.id"
                      :quest="quest"
                      :vault-id="vaultId"
                      status="ready"
                      @claim="handleClaimRewards"
                    />
                  </div>
                </div>

                <!-- Active Quests Section -->
                <div v-if="travellingOrActiveQuests.length > 0" class="quest-section">
                  <div class="quest-grid">
                    <QuestCard
                      v-for="quest in travellingOrActiveQuests"
                      :key="quest.id"
                      :quest="quest"
                      :vault-id="vaultId"
                      :status="isQuestReturning(quest) ? 'returning' : 'active'"
                      :party-members="questPartyMembersMap[quest.id] || []"
                      @assign-party="handleAssignParty"
                    />
                  </div>
                </div>

                <!-- Empty State -->
                <div
                  v-if="readyToClaimQuests.length === 0 && travellingOrActiveQuests.length === 0"
                  class="empty-state"
                >
                  <Icon icon="mdi:inbox" class="text-8xl mb-6 opacity-30" />
                  <p>No active quests. Start one from the Available tab.</p>
                </div>
              </div>

              <!-- Available Quests -->
              <div v-if="activeTab === 'available'" class="tab-content">
                <!-- Available Quests Section -->
                <div v-if="filteredAvailableQuests.length > 0" class="quest-section">
                  <div class="filter-row">
                    <Select
                      :model-value="availableSort"
                      @update:model-value="onAvailableSortChange"
                    >
                      <SelectTrigger
                        size="sm"
                        class="min-w-[9rem] border-theme-glow rounded-md px-3 py-2 text-[0.8125rem] opacity-[0.85] hover:opacity-100 hover:shadow-[0_0_8px_var(--color-theme-glow)]"
                        aria-label="Sort available quests"
                      >
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem
                          v-for="option in availableSortOptions"
                          :key="option.value"
                          :value="option.value"
                        >
                          {{ option.label }}
                        </SelectItem>
                      </SelectContent>
                    </Select>
                    <span v-if="showAllQuests" class="filter-hint">(Showing All)</span>
                    <!-- Raw checkbox: no Checkbox/Switch primitive is vendored (docs/frontend/RAW_NATIVE_CONTROLS.md). -->
                    <label class="toggle-label">
                      <input v-model="showAllQuests" type="checkbox" class="toggle-input" />
                      <span class="toggle-text">Show All</span>
                    </label>
                  </div>
                  <div class="quest-grid">
                    <QuestCard
                      v-for="quest in sortedAvailableQuests"
                      :key="quest.id"
                      :quest="quest"
                      :vault-id="vaultId"
                      :status="quest.is_locked ? 'locked' : 'available'"
                      :is-locked="quest.is_locked"
                      :party-members="questPartyMembersMap[quest.id] || []"
                      @start="vaultId && questStore.startQuest(vaultId, $event)"
                      @assign-party="handleAssignParty"
                    />
                  </div>
                </div>

                <!-- Empty State -->
                <div v-else class="empty-state">
                  <Icon icon="mdi:inbox" class="text-8xl mb-6 opacity-30" />
                  <p v-if="showAllQuests">No quests available at the moment</p>
                  <p v-else>
                    No unlocked quests available. Complete previous quests to unlock more.
                  </p>
                </div>
              </div>

              <!-- Completed Quests -->
              <div v-if="activeTab === 'completed'" class="tab-content">
                <div v-if="completedQuests.length === 0" class="empty-state">
                  <Icon
                    icon="mdi:checkbox-marked-circle-outline"
                    class="text-8xl mb-6 opacity-30"
                  />
                  <p>No completed quests yet</p>
                </div>

                <div v-else class="quest-section">
                  <div class="quest-grid">
                    <QuestCard
                      v-for="quest in completedQuests"
                      :key="quest.id"
                      :quest="quest"
                      :vault-id="vaultId"
                      status="completed"
                      @view="openQuest"
                    />
                  </div>
                </div>
              </div>
            </Tabs>
          </div>

          <!-- Party Selection Modal -->
          <PartySelectionModal
            v-model="showPartyModal"
            :quest="selectedQuest"
            :vault-id="vaultId"
            :dwellers="dwellerStore.dwellers"
            :current-party="questPartyMembers"
            @assign="handleAssignAndStart"
          />

          <QuestRewardsModal
            :quest="claimQuest"
            :show="showClaimModal"
            :is-submitting="isClaiming"
            @close="closeClaimModal"
            @confirm="confirmClaimRewards"
          />

          <!-- Quest detail modal: deep-linked via ?quest=<id>; the list stays mounted behind it. -->
          <QuestDetailModal
            v-if="selectedQuestId"
            :quest-id="selectedQuestId"
            :vault-id="vaultId"
            @close="closeQuest"
            @select="openQuest"
            @start="handleStartFromModal"
          />
        </PageContentRail>
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
  font-weight: 700;
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
}

/* Locked State */
.locked-container {
  max-width: 800px;
  margin: 80px auto;
  padding: 60px 40px;
  background-color: var(--color-surface-light);
  border: 3px solid var(--color-theme-primary);
  border-radius: 12px;
  text-align: center;
  box-shadow: var(--glow-1);
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
  width: 100%;
}

/* Section Title */
.quest-section {
  margin-bottom: 32px;
}

.filter-row {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.filter-hint {
  font-size: 0.75rem;
  color: var(--color-theme-accent);
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
  background: var(--color-surface-raised);
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
  background: var(--color-gray-50);
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
