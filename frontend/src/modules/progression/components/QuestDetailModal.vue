<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import { useQuestStore } from '../stores/quest'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/core/components/ui/dialog'
import QuestRewardsModal from './QuestRewardsModal.vue'
import QuestRewardList from './QuestRewardList.vue'
import QuestRequirementList from './QuestRequirementList.vue'
import { Button } from '@/core/components/ui/button'
import { Progress } from '@/core/components/ui/progress'
import { parseStartTimeMs } from '@/modules/exploration/composables/useExplorationProgress'
import type { QuestPartyMember, VaultQuest } from '../models/quest'
import { isQuestReturning, describeGrantedReward, formatGrantedReward } from '../models/quest'

const props = defineProps<{
  questId: string
  vaultId: string
}>()

const emit = defineEmits<{
  close: []
  select: [questId: string]
}>()

const router = useRouter()
const questStore = useQuestStore()
const authStore = useAuthStore()
const { filter: dwellerStore } = useDwellerStore()

const quest = ref<VaultQuest | null>(null)
const partyLinks = ref<QuestPartyMember[]>([])
const isLoading = ref(true)
const error = ref<string | null>(null)

async function loadParty() {
  if (!props.vaultId || !props.questId) return
  try {
    partyLinks.value = await questStore.getParty(props.vaultId, props.questId)
  } catch {
    partyLinks.value = []
  }
}

async function loadQuest() {
  if (!props.vaultId || !props.questId) {
    error.value = 'Missing vault or quest ID'
    isLoading.value = false
    return
  }

  isLoading.value = true
  error.value = null
  try {
    await questStore.fetchVaultQuests(props.vaultId)
    const vaultQuest = questStore.vaultQuests.find((q) => q.id === props.questId)

    if (vaultQuest) {
      quest.value = vaultQuest
    } else {
      await questStore.fetchAllQuests()
      const generalQuest = questStore.quests.find((q) => q.id === props.questId)
      if (generalQuest) {
        quest.value = {
          ...generalQuest,
          is_visible: false,
          is_locked: true,
          lock_reason: 'Not available in this vault',
          is_completed: false,
          started_at: null,
          duration_minutes: null,
          return_started_at: null,
          return_completes_at: null,
          completed_at: null,
        }
      } else {
        error.value = 'Quest not found'
      }
    }

    const token = authStore.token || localStorage.getItem('token')?.replace(/^"|"$/g, '')
    if (props.vaultId && token) {
      await dwellerStore.fetchDwellersByVault(props.vaultId, token)
    }
    void loadParty()
  } catch {
    error.value = 'Failed to load quest details'
  } finally {
    isLoading.value = false
  }
}

// Chain navigation reuses this component, so reload when the quest prop changes.
watch(() => props.questId, () => void loadQuest(), { immediate: true })

const isChainQuest = computed(() => {
  return Boolean(quest.value?.chain_id)
})

const chainQuests = computed(() => {
  const current = quest.value
  if (!current?.chain_id) return []
  const merged = new Map<string, { id: string, title: string, chainOrder: number, isCompleted: boolean }>()
  for (const q of questStore.quests) {
    if (q.chain_id !== current.chain_id || merged.has(q.id)) continue
    merged.set(q.id, { id: q.id, title: q.title, chainOrder: q.chain_order ?? 0, isCompleted: false })
  }
  for (const q of questStore.vaultQuests) {
    if (q.chain_id !== current.chain_id) continue
    merged.set(q.id, { id: q.id, title: q.title, chainOrder: q.chain_order ?? 0, isCompleted: q.is_completed })
  }
  return [...merged.values()]
    .sort((a, b) => a.chainOrder - b.chainOrder)
    .map((row) => ({ ...row, isCurrent: row.id === current.id }))
})

function goToChainQuest(chainQuestId: string) {
  emit('select', chainQuestId)
}

const grantedRewards = computed(() => quest.value?.granted_rewards ?? [])

const completedAtLabel = computed(() => {
  const completedAt = quest.value?.completed_at
  if (!completedAt) return ''
  return new Date(parseStartTimeMs(completedAt)).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
})

function goToDweller(dwellerId: string) {
  if (props.vaultId) {
    void router.push({ name: 'dwellerDetail', params: { id: props.vaultId, dwellerId } })
  }
}

const hasPrerequisites = computed(() => {
  return quest.value?.quest_requirements && quest.value.quest_requirements.length > 0
})

const prerequisitesMet = computed(() => {
  if (!hasPrerequisites.value || !quest.value) return true
  return quest.value.is_visible || quest.value.is_completed
})

const canStart = computed(() => {
  return (
    Boolean(quest.value?.is_visible) &&
    !quest.value?.is_completed &&
    quest.value?.started_at == null &&
    prerequisitesMet.value &&
    !quest.value?.is_locked
  )
})

const isReturning = computed(() => (quest.value ? isQuestReturning(quest.value) : false))

const isInProgress = computed(() => {
  return (
    quest.value?.started_at != null &&
    !quest.value?.is_completed &&
    !quest.value?.is_reward_ready &&
    !isReturning.value
  )
})

const isCompleted = computed(() => {
  return quest.value?.is_completed
})
const isRewardReady = computed(() => quest.value?.is_reward_ready && !quest.value?.is_completed)
const showClaimModal = ref(false)

const now = ref(Date.now())
let returnTimer: ReturnType<typeof setInterval> | null = null
const returnMinutesRemaining = computed(() => {
  if (!quest.value?.return_completes_at) return 0
  const remaining = parseStartTimeMs(quest.value.return_completes_at) - now.value
  return Math.max(0, Math.ceil(remaining / 60_000))
})

const tracking = computed(() => {
  const current = quest.value
  if (!current?.started_at || current.is_completed) return null
  const at = now.value
  if (isReturning.value && current.return_started_at && current.return_completes_at) {
    const start = parseStartTimeMs(current.return_started_at)
    const end = parseStartTimeMs(current.return_completes_at)
    const pct = Math.min(100, Math.max(0, ((at - start) / Math.max(1, end - start)) * 100))
    return { title: 'Returning Home', detail: `${returnMinutesRemaining.value}m remaining`, pct }
  }
  if (!current.duration_minutes) return null
  const start = parseStartTimeMs(current.started_at)
  const total = current.duration_minutes * 60_000
  const pct = Math.min(100, Math.max(0, ((at - start) / total) * 100))
  const remainingMs = Math.max(0, start + total - at)
  const hours = Math.floor(remainingMs / 3_600_000)
  const minutes = Math.ceil((remainingMs % 3_600_000) / 60_000)
  return { title: 'Mission Progress', detail: hours > 0 ? `${hours}h ${minutes}m left` : `${minutes}m left`, pct }
})

const roster = computed(() =>
  partyLinks.value.map((link) => {
    const dweller = dwellerStore.dwellers.find((d) => d.id === link.dweller_id) ?? null
    return { link, dweller }
  })
)

onMounted(() => {
  returnTimer = setInterval(() => {
    now.value = Date.now()
    if (isReturning.value && returnMinutesRemaining.value <= 0) void refreshQuestAfterArrival()
  }, 30_000)
})

onUnmounted(() => {
  if (returnTimer) clearInterval(returnTimer)
})

const closeClaimModal = () => {
  showClaimModal.value = false
}

let isRefreshingQuest = false
async function refreshQuestAfterArrival() {
  if (!props.vaultId || !props.questId || isRefreshingQuest) return
  isRefreshingQuest = true
  try {
    await questStore.fetchVaultQuests(props.vaultId, { silent: true })
    const updated = questStore.vaultQuests.find((q) => q.id === props.questId)
    if (updated) quest.value = updated
    await loadParty()
  } catch {
    // Background poll: ignore and retry on the next tick.
  } finally {
    isRefreshingQuest = false
  }
}

const openClaimModal = () => {
  showClaimModal.value = true
}

const handleStartQuest = async () => {
  if (!props.vaultId || !props.questId) return
  await questStore.assignQuest(props.vaultId, props.questId, true)
  await questStore.fetchVaultQuests(props.vaultId)
  const updatedQuest = questStore.vaultQuests.find((q) => q.id === props.questId)
  if (updatedQuest) {
    quest.value = updatedQuest
  }
  await loadParty()
}

const confirmClaimRewards = async () => {
  if (!props.vaultId || !props.questId) return
  await questStore.claimQuestRewards(props.vaultId, props.questId)
  closeClaimModal()
  await questStore.fetchVaultQuests(props.vaultId)
  quest.value = questStore.vaultQuests.find((item) => item.id === props.questId) ?? quest.value
  await loadParty()
}
</script>

<template>
  <Dialog :open="true" @update:open="(open) => { if (!open) emit('close') }">
    <DialogContent
      class="flex max-h-[80vh] w-full max-w-3xl flex-col gap-0 overflow-hidden rounded-lg border-2 border-theme-primary p-0 text-base crt-screen sm:max-w-3xl"
    >
      <DialogHeader
        class="flex flex-shrink-0 flex-row items-center gap-3 border-b border-theme-primary/25 bg-theme-primary/5 p-6 pb-4"
      >
        <DialogTitle class="quest-title terminal-glow">{{ quest?.title ?? 'Quest' }}</DialogTitle>
      </DialogHeader>

      <div class="flex-1 overflow-y-auto px-5 pt-5 pb-5">
        <div v-if="isLoading" class="loading-state">
          <Icon icon="mdi:loading" class="animate-spin text-4xl" />
          <p>Loading quest details...</p>
        </div>

        <div v-else-if="error" class="error-state">
          <Icon icon="mdi:alert-circle" class="text-6xl mb-4" />
          <p>{{ error }}</p>
        </div>

        <div v-else-if="quest" class="quest-detail">
          <div class="quest-header-section">
            <div class="quest-banner-row">
              <div class="quest-meta">
                <div v-if="isCompleted" class="quest-banner quest-banner--completed">
                  <Icon icon="mdi:seal" class="banner-icon" />
                  <span>Quest Completed - Rewards Claimed<span v-if="completedAtLabel"> · {{ completedAtLabel }}</span></span>
                </div>
                <div v-else-if="isReturning" class="quest-banner quest-banner--returning">
                  <Icon icon="mdi:home-import-outline" class="banner-icon" />
                  Party Travelling Home
                </div>
                <div v-else-if="isInProgress" class="quest-banner quest-banner--active">
                  <Icon icon="mdi:progress-check" class="banner-icon" />
                  Quest In Progress
                </div>
              </div>
            </div>

            <p class="quest-description">{{ quest.long_description }}</p>
          </div>

          <div class="quest-content-grid" :class="{ 'is-completed': isCompleted }">
            <div class="quest-main-content">
              <div class="quest-duo">
                <QuestRequirementList
                  v-if="hasPrerequisites"
                  :requirements="quest.quest_requirements ?? []"
                  :is-met="() => prerequisitesMet"
                />
                <div v-if="isCompleted && grantedRewards.length > 0" class="quest-section">
                  <div class="section-label">
                    <Icon icon="mdi:treasure-chest" class="inline-icon" />
                    REWARDS
                  </div>
                  <ul class="granted-list">
                    <li v-for="(reward, index) in grantedRewards" :key="index" class="granted-row">
                      <Icon :icon="describeGrantedReward(reward).icon" class="granted-icon" />
                      <span>{{ formatGrantedReward(reward) }}</span>
                    </li>
                  </ul>
                </div>
                <QuestRewardList
                  v-else
                  :rewards="quest.quest_rewards ?? []"
                  :fallback-text="quest.rewards"
                />
              </div>

              <div v-if="tracking" class="quest-section">
                <div class="section-label">
                  <Icon icon="mdi:radar" class="inline-icon" />
                  {{ tracking.title.toUpperCase() }}
                </div>
                <Progress :model-value="tracking.pct" class="h-2" />
                <p class="tracking-detail">{{ tracking.detail }}</p>
              </div>

              <div v-if="quest.started_at" class="quest-section">
                <div class="section-label">
                  <Icon icon="mdi:account-group" class="inline-icon" />
                  {{ isCompleted ? 'COMPLETED BY' : 'PARTY' }} ({{ roster.length }})
                </div>
                <ul v-if="roster.length > 0" class="party-list">
                  <li v-for="row in roster" :key="row.link.id" class="party-row">
                    <button
                      v-if="row.dweller"
                      class="party-row-button"
                      @click="goToDweller(row.dweller.id)"
                    >
                      <Icon icon="mdi:account" class="member-icon" />
                      <span class="member-name">
                        {{ `${row.dweller.first_name} ${row.dweller.last_name}` }}
                      </span>
                      <span class="member-level">Lv.{{ row.dweller.level || 1 }}</span>
                      <Icon icon="mdi:chevron-right" class="member-chevron" />
                    </button>
                    <span v-else class="party-row-unknown">
                      <Icon icon="mdi:account" class="member-icon" />
                      <span class="member-name">Unknown dweller</span>
                    </span>
                  </li>
                </ul>
                <p v-else class="empty-text">No party assigned to this quest.</p>
              </div>

              <div v-if="isChainQuest" class="quest-section">
                <div class="section-label">
                  <Icon icon="mdi:link-variant" class="inline-icon" />
                  QUEST CHAIN
                </div>
                <ul class="chain-list">
                  <li
                    v-for="row in chainQuests"
                    :key="row.id"
                    class="chain-row"
                    :class="{ current: row.isCurrent, completed: row.isCompleted }"
                  >
                    <button
                      v-if="!row.isCurrent"
                      class="chain-row-button"
                      @click="goToChainQuest(row.id)"
                    >
                      <span class="chain-row-title">{{ row.title }}</span>
                      <Icon :icon="row.isCompleted ? 'mdi:check-circle' : 'mdi:circle-outline'" class="chain-row-icon" />
                      <span class="chain-row-state">{{ row.isCompleted ? 'Completed' : 'Upcoming' }}</span>
                    </button>
                    <span v-else class="chain-row-current">
                      <span class="chain-row-title">{{ row.title }}</span>
                      <Icon icon="mdi:play-circle" class="chain-row-icon" />
                      <span class="chain-row-state">Current</span>
                    </span>
                  </li>
                </ul>
              </div>
            </div>

            <div v-if="!isCompleted" class="quest-sidebar">
              <div class="action-section">
                <Button
                  v-if="canStart"
                  variant="default"
                  class="action-btn"
                  @click="handleStartQuest"
                >
                  <Icon icon="mdi:play" class="btn-icon" />
                  Start Quest
                </Button>

                <Button v-else-if="isRewardReady" variant="default" class="action-btn" @click="openClaimModal">
                  <Icon icon="mdi:treasure-chest" class="btn-icon" />
                  Claim Rewards
                </Button>

                <Button v-else-if="isReturning" disabled variant="secondary" class="action-btn">
                  <Icon icon="mdi:home-import-outline" class="btn-icon" />
                  Party travelling home — returns in {{ returnMinutesRemaining }}m
                </Button>

                <div v-else-if="isInProgress" class="active-message">
                  <Icon icon="mdi:progress-clock" class="message-icon" />
                  <span>Quest in progress — rewards will be delivered on return</span>
                </div>

                <div v-else-if="!prerequisitesMet || quest.is_locked" class="locked-message">
                  <Icon icon="mdi:lock" class="message-icon" />
                  <span>{{ quest.is_locked ? (quest.lock_reason ?? 'Quest locked') : 'Prerequisites not met' }}</span>
                </div>
              </div>

              <QuestRewardsModal
                :quest="quest"
                :show="showClaimModal"
                @close="closeClaimModal"
                @confirm="confirmClaimRewards"
              />
            </div>
          </div>
        </div>
      </div>
    </DialogContent>
  </Dialog>
</template>

<style scoped>
.loading-state,
.error-state {
  text-align: center;
  padding: 48px 24px;
  color: var(--color-theme-primary);
}

.error-state p {
  margin: 0;
}

.animate-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.quest-title {
  font-size: 1.5rem;
  font-weight: bold;
  color: var(--color-theme-primary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin: 0;
}

.quest-header-section {
  margin-bottom: 32px;
}

.quest-banner-row {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.quest-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.quest-banner {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 12px 24px;
  border-radius: 4px;
  font-weight: bold;
  font-size: 1.1rem;
}

.quest-content-grid.is-completed {
  grid-template-columns: 1fr;
}

.quest-banner--completed {
  background: color-mix(in srgb, var(--color-theme-primary) 10%, transparent);
  border: 2px solid var(--color-theme-primary);
  color: var(--color-theme-primary);
}

.quest-banner--active {
  background: var(--color-theme-glow);
  border: 2px solid var(--color-theme-accent);
  color: var(--color-theme-accent);
}

.quest-banner--returning {
  background: var(--color-theme-glow);
  border: 2px solid var(--color-theme-secondary);
  color: var(--color-theme-secondary);
}

.banner-icon {
  font-size: 1.5rem;
}

.quest-content-grid {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 24px;
}

@media (max-width: 1024px) {
  .quest-content-grid {
    grid-template-columns: 1fr;
  }
  .quest-duo {
    grid-template-columns: 1fr;
  }
}

.quest-main-content {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.quest-section {
  margin-bottom: 4px;
}

.section-label {
  font-size: 0.75rem;
  font-weight: bold;
  color: var(--color-theme-accent);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 4px;
}

.quest-description {
  font-size: 1.1rem;
  line-height: 1.8;
  color: var(--color-theme-primary);
  margin: 0 0 32px 0;
}

.quest-main-content :deep(.section-label) {
  font-size: 1rem;
}

.quest-duo {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}

.granted-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.granted-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.9rem;
  color: var(--color-theme-primary);
}

.granted-icon {
  color: var(--color-theme-accent);
  flex-shrink: 0;
}

.tracking-detail {
  margin-top: 12px;
  font-size: 0.9rem;
  color: var(--color-theme-primary);
}

.party-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.party-row {
  padding: 2px 0;
  font-size: 0.9rem;
}

.party-row-button {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 0;
  background: none;
  border: none;
  font: inherit;
  color: inherit;
  cursor: pointer;
  text-align: left;
}

.party-row-button:hover .member-name {
  color: var(--color-theme-accent);
}

.member-chevron {
  margin-left: auto;
  color: var(--color-theme-accent);
  flex-shrink: 0;
}

.party-row-unknown {
  display: flex;
  align-items: center;
  gap: 8px;
}

.member-icon {
  font-size: 1.25rem;
  color: var(--color-theme-accent);
  flex-shrink: 0;
}

.member-name {
  font-weight: bold;
  overflow-wrap: anywhere;
}

.member-level {
  color: var(--color-theme-accent);
}

.empty-text {
  font-size: 0.9rem;
  opacity: 0.7;
}

.chain-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.chain-row {
  border-radius: 4px;
  font-size: 0.9rem;
}

.chain-row.current {
  color: var(--color-theme-accent);
}

.chain-row.completed {
  opacity: 0.75;
}

.chain-row-icon {
  font-size: 1rem;
  flex-shrink: 0;
}

.chain-row.completed .chain-row-icon {
  color: var(--color-theme-primary);
}

.chain-row.current .chain-row-icon {
  color: var(--color-theme-accent);
}

.chain-row:not(.completed):not(.current) .chain-row-icon {
  opacity: 0.5;
}

.chain-row-button {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 4px 0;
  background: none;
  border: none;
  font: inherit;
  color: inherit;
  cursor: pointer;
  text-align: left;
}

.chain-row-current {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
}

.chain-row-title {
  font-weight: bold;
  overflow-wrap: anywhere;
  flex: 1;
}

.chain-row-state {
  margin-left: auto;
  font-size: 0.8rem;
  opacity: 0.7;
  white-space: nowrap;
}

.quest-sidebar {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.action-section {
  margin-top: auto;
}

.action-btn {
  width: 100%;
  padding: 16px;
  font-size: 1.1rem;
}

.btn-icon {
  margin-right: 8px;
}

.active-message,
.locked-message {
  padding: 16px;
  border-radius: 4px;
  text-align: center;
  font-weight: bold;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.active-message {
  background: color-mix(in srgb, var(--color-theme-accent) 10%, transparent);
  border: 2px solid var(--color-theme-accent);
  color: var(--color-theme-accent);
}

.locked-message {
  background: rgba(255, 102, 0, 0.1);
  border: 2px solid var(--color-quest-locked);
  color: var(--color-quest-locked);
}

.message-icon {
  font-size: 1.5rem;
}

.inline-icon {
  display: inline;
  vertical-align: middle;
}
</style>
