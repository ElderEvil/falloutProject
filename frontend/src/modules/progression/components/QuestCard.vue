<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { Badge } from '@/core/components/ui/badge'
import { Button } from '@/core/components/ui/button'
import { Card } from '@/core/components/ui/card'
import { Progress } from '@/core/components/ui/progress'
import { useQuestStore } from '@/modules/progression/stores/quest'
import { useDwellerFilterStore } from '@/modules/dwellers/stores/dwellerFilter'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import { parseStartTimeMs } from '@/modules/exploration/composables/useExplorationProgress'
import type { QuestPartyMember, QuestRequirement, VaultQuest } from '../models/quest'
import { formatQuestReward, questRewardIcon } from '../models/quest'

const questStore = useQuestStore()
const dwellerFilterStore = useDwellerFilterStore()

interface Props {
  quest: VaultQuest
  vaultId: string
  status: 'available' | 'active' | 'returning' | 'ready' | 'completed' | 'locked'
  partyMembers?: DwellerShort[]
  isLocked?: boolean
}

const { partyMembers, isLocked = false, quest, status, vaultId } = defineProps<Props>()

const emit = defineEmits<{
  start: [questId: string]
  claim: [questId: string]
  view: [questId: string]
  assignParty: [questId: string]
}>()

const timeRemaining = ref<string | null>(null)
let timerInterval: ReturnType<typeof setInterval> | null = null

const updateTimer = () => {
  if (status === 'returning') {
    if (!quest.return_completes_at) {
      timeRemaining.value = null
      return
    }
    const remaining = parseStartTimeMs(quest.return_completes_at) - Date.now()
    if (remaining <= 0) {
      timeRemaining.value = '00:00:00'
      if (timerInterval) {
        clearInterval(timerInterval)
        timerInterval = null
      }
      return
    }
    const hours = Math.floor(remaining / (1000 * 60 * 60))
    const minutes = Math.floor((remaining % (1000 * 60 * 60)) / (1000 * 60))
    const seconds = Math.floor((remaining % (1000 * 60)) / 1000)
    timeRemaining.value = `${hours.toString().padStart(2, '0')}:${minutes
      .toString()
      .padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`
    return
  }

  if (!quest.started_at || !quest.duration_minutes) {
    timeRemaining.value = null
    return
  }

  const startTime = parseStartTimeMs(quest.started_at)
  const durationMs = quest.duration_minutes * 60 * 1000
  const endTime = startTime + durationMs
  const now = Date.now()
  const remaining = endTime - now

  if (remaining <= 0) {
    timeRemaining.value = '00:00:00'
    if (timerInterval) {
      clearInterval(timerInterval)
      timerInterval = null
    }
    return
  }

  const hours = Math.floor(remaining / (1000 * 60 * 60))
  const minutes = Math.floor((remaining % (1000 * 60 * 60)) / (1000 * 60))
  const seconds = Math.floor((remaining % (1000 * 60)) / 1000)

  timeRemaining.value = `${hours.toString().padStart(2, '0')}:${minutes
    .toString()
    .padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`
}

const questProgress = computed(() => {
  void timeRemaining.value
  if (!quest.started_at || !quest.duration_minutes) return 0

  const elapsed = Date.now() - parseStartTimeMs(quest.started_at)
  return Math.min(100, Math.max(0, (elapsed / (quest.duration_minutes * 60 * 1000)) * 100))
})

const returnProgress = computed(() => {
  void timeRemaining.value
  if (!quest.return_started_at || !quest.return_completes_at) return 0

  const start = parseStartTimeMs(quest.return_started_at)
  const total = parseStartTimeMs(quest.return_completes_at) - start
  if (total <= 0) return 100
  return Math.min(100, Math.max(0, ((Date.now() - start) / total) * 100))
})

const displayedQuestProgress = computed(() => {
  if (status === 'ready') return 100
  if (status === 'returning') return returnProgress.value
  return questProgress.value
})
const questProgressLabel = computed(() => {
  if (status === 'returning') return `${Math.round(displayedQuestProgress.value)}% home`
  return `${Math.round(displayedQuestProgress.value)}% complete`
})

const startTimer = () => {
  if (timerInterval) {
    clearInterval(timerInterval)
  }
  if (
    (status === 'active' || status === 'returning') &&
    quest.started_at &&
    quest.duration_minutes
  ) {
    updateTimer()
    timerInterval = setInterval(updateTimer, 1000)
  }
}

const stopTimer = () => {
  if (timerInterval) {
    clearInterval(timerInterval)
    timerInterval = null
  }
}

watch(
  () => [status, quest.started_at, quest.return_completes_at],
  () => {
    if (
      (status === 'active' || status === 'returning') &&
      quest.started_at &&
      quest.duration_minutes
    ) {
      startTimer()
    } else {
      stopTimer()
    }
  },
  { immediate: true }
)

onMounted(() => {
  startTimer()
})

onUnmounted(() => {
  stopTimer()
})

const hasParty = computed(() => partyMembers && partyMembers.length > 0)
const isStateQuest = computed(() => ['building', 'population', 'training'].includes(quest.quest_category ?? ''))

const typeColors: Record<string, { bg: string; text: string; border: string }> = {
  main: { bg: 'var(--color-quest-main)', text: '#000000', border: 'var(--color-quest-main)' },
  side: { bg: 'var(--color-quest-side)', text: 'var(--color-theme-primary)', border: 'var(--color-quest-side)' },
  daily: { bg: 'var(--color-quest-daily)', text: '#000000', border: 'var(--color-quest-daily)' },
  event: { bg: 'var(--color-quest-event)', text: '#ffffff', border: 'var(--color-quest-event)' },
  repeatable: { bg: 'var(--color-theme-primary)', text: '#000000', border: 'var(--color-theme-primary)' },
}

const typeColor = computed(() => {
  return typeColors[quest.quest_type] || typeColors.side
})

const typeLabel = computed(() => {
  const questType = quest.quest_type || 'side'
  return questType.charAt(0).toUpperCase() + questType.slice(1)
})

// Side quests share the bordered chip styling with building/exploration categories.
const isSideQuest = computed(() => (quest.quest_type || 'side') === 'side')

const isBorderedCategory = computed(() =>
  ['building', 'exploration'].includes(quest.quest_category ?? '')
)

const isChainQuest = computed(() => {
  return quest.chain_id !== null
})

const chainPosition = computed(() => {
  if (!isChainQuest.value) return null
  return quest.chain_order > 0 ? `Quest ${quest.chain_order}` : 'Chain Quest'
})

// Get the previous quest name for locked quests
const previousQuestName = computed(() => {
  if (!quest.previous_quest_id) return null
  // Search in vaultQuests first, then fall back to all quests
  const previousQuest =
    questStore.vaultQuests.find((q) => q.id === quest.previous_quest_id) ||
    questStore.quests.find((q) => q.id === quest.previous_quest_id)
  return previousQuest?.title || null
})

const hasPrerequisites = computed(() => {
  return quest.quest_requirements && quest.quest_requirements.length > 0
})

const prerequisitesMet = computed(() => {
  if (!hasPrerequisites.value) return true
  // For now, assume prerequisites are met if quest is active or completed
  // In a real implementation, this would check actual vault state
  return status !== 'available'
})

const getRequirementCount = (requirementData: Record<string, unknown>): number => {
  const count = requirementData.count
  return typeof count === 'number' ? count : 0
}

const statLabel = (stat: unknown): string => {
  const label = String(stat ?? 'stat').replace(/_/g, ' ')
  return label.charAt(0).toUpperCase() + label.slice(1)
}

function isLevelRequirementMet(requirementData: Record<string, unknown>): boolean {
  const level = requirementData.level
  if (typeof level !== 'number') return false
  if (dwellerFilterStore.dwellers.length === 0) return false
  const required = getRequirementCount(requirementData) || 1
  const qualified = dwellerFilterStore.dwellers.filter((d) => (d.level ?? 0) >= level).length
  return qualified >= required
}

function isQuestRequirementMet(requirementData: Record<string, unknown>): boolean {
  if (typeof requirementData.quest_id !== 'string') return false
  const found = questStore.vaultQuests.find((q) => q.id === requirementData.quest_id)
  if (!found) return false
  return found.is_completed === true
}

function isRequirementMet(req: QuestRequirement): boolean {
  if (req.requirement_type === 'level' && req.requirement_data) {
    return isLevelRequirementMet(req.requirement_data)
  }
  if (req.requirement_type === 'quest_completed' && req.requirement_data) {
    return isQuestRequirementMet(req.requirement_data)
  }
  return prerequisitesMet.value
}

function requirementIcon(req: QuestRequirement): string {
  if (!isRequirementMet(req)) return 'mdi:lock'
  return req.requirement_type === 'level' || req.requirement_type === 'quest_completed'
    ? 'mdi:lock-open'
    : 'mdi:check-circle'
}

const roomDisplayName = (requirementData: Record<string, unknown>): string => {
  const slug = requirementData.room_type
  if (typeof slug !== 'string' || slug.length === 0) return 'room'
  return slug
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

function questRequirementName(requirementData: Record<string, unknown>): string {
  if (typeof requirementData.quest_name === 'string' && requirementData.quest_name.length > 0) {
    return requirementData.quest_name
  }
  if (typeof requirementData.quest_id === 'string') {
    const found =
      questStore.vaultQuests.find((q) => q.id === requirementData.quest_id) ??
      questStore.quests.find((q) => q.id === requirementData.quest_id)
    if (found?.title) return found.title
  }
  return 'Previous quest'
}

const actionButtonText = computed(() => {
  if (isLocked) return 'Locked'
  return {
    available: isStateQuest.value ? 'Check Objective' : 'Start Quest',
    active: 'In Progress',
    returning: 'Travelling Home',
    ready: 'Claim Rewards',
    completed: 'View Details',
    locked: 'Locked',
  }[status]
})

const cardBorderColor = computed(() => {
  if (isLocked) return 'var(--color-quest-locked)'
  return {
    available: typeColor.value.border,
    active: 'var(--color-theme-accent)',
    returning: 'var(--color-theme-secondary)',
    ready: 'var(--color-rarity-legendary)',
    completed: 'var(--color-quest-muted)',
    locked: 'var(--color-quest-locked)',
  }[status]
})

const isButtonDisabled = computed(() => {
  return isLocked || status === 'active' || status === 'returning'
})

const handleAction = () => {
  if (isLocked) {
    return // Don't do anything for locked quests
  }
  switch (status) {
    case 'available':
      if (isStateQuest.value || hasParty.value) {
        emit('start', quest.id)
      } else {
        emit('assignParty', quest.id)
      }
      break
    case 'active':
    case 'returning':
      break
    case 'ready':
      emit('claim', quest.id)
      break
    case 'completed':
      emit('view', quest.id)
      break
  }
}
</script>

<template>
  <Card
    class="quest-card flex h-full flex-col"
    :style="{ borderColor: cardBorderColor }"
    :class="{ 'completed-quest': status === 'completed' }"
  >
    <div class="quest-card-content flex-1">
      <!-- Header -->
      <div class="quest-header">
      <h3 class="quest-title">{{ quest.title }}</h3>
      <div class="quest-badges">
        <Badge
          :variant="isSideQuest ? 'outline' : 'default'"
          :style="isSideQuest ? undefined : { backgroundColor: typeColor.bg, color: typeColor.text }"
          class="type-badge"
        >
          {{ typeLabel }}
        </Badge>
        <Badge
          v-if="quest.quest_category"
          :variant="isBorderedCategory ? 'outline' : 'secondary'"
          class="category-badge"
        >
          {{ quest.quest_category }}
        </Badge>
        <Badge v-if="isChainQuest" variant="outline" class="chain-badge">
          <Icon icon="mdi:link-variant" class="inline-icon" />
          {{ chainPosition }}
        </Badge>
        <Badge v-if="isLocked" variant="outline" class="locked-badge">
          <Icon icon="mdi:lock" class="inline-icon" />
          LOCKED
        </Badge>
      </div>
    </div>

    <!-- Description -->
    <p class="quest-description">{{ quest.short_description }}</p>

    <!-- Lock Reason (backend-owned, e.g. Overseer's Office / chain / requirements) -->
    <div v-if="isLocked && (quest.lock_reason || previousQuestName)" class="quest-section locked-info">
      <div class="section-label">
        <Icon icon="mdi:lock-alert" class="inline-icon" />
        LOCKED
      </div>
      <div v-if="quest.lock_reason" class="locked-message">
        <Icon icon="mdi:lock" class="locked-icon" />
        {{ quest.lock_reason }}
      </div>
      <div v-if="previousQuestName && !quest.lock_reason" class="locked-message">
        <Icon icon="mdi:arrow-left" class="locked-icon" />
        Complete "{{ previousQuestName }}" to unlock
      </div>
    </div>

    <!-- Divider -->
    <div class="quest-divider"></div>

    <!-- Prerequisites (if any) -->
    <div v-if="hasPrerequisites" class="quest-section">
      <div class="section-label">
        <Icon icon="mdi:clipboard-check" class="inline-icon" />
        REQUIREMENTS
      </div>
      <ul class="prerequisites-list">
          <li
            v-for="req in quest.quest_requirements"
            :key="req.id"
            class="prerequisite-item"
            :class="{ met: isRequirementMet(req), unmet: !isRequirementMet(req) }"
          >
            <Icon
              :icon="requirementIcon(req)"
              class="prerequisite-icon"
            />
          <span class="prerequisite-text">
            <template v-if="req.requirement_type === 'level' && req.requirement_data">
              Requires Level {{ req.requirement_data.level || 1 }}+ dweller
              <span v-if="getRequirementCount(req.requirement_data) > 1">
                (x{{ getRequirementCount(req.requirement_data) }})
              </span>
            </template>
            <template v-else-if="req.requirement_type === 'item' && req.requirement_data">
              Requires {{ req.requirement_data.item_name || req.requirement_data.name || req.requirement_data.item_id }}
              <span v-if="getRequirementCount(req.requirement_data) > 1">
                (x{{ getRequirementCount(req.requirement_data) }})
              </span>
            </template>
            <template v-else-if="req.requirement_type === 'attack' && req.requirement_data">
              Requires {{ req.requirement_data.attack || 1 }}+ Attack
              <span v-if="getRequirementCount(req.requirement_data) > 1">
                (x{{ getRequirementCount(req.requirement_data) }})
              </span>
            </template>
            <template v-else-if="req.requirement_type === 'stat' && req.requirement_data">
              Requires {{ req.requirement_data.value || 1 }}+ {{ statLabel(req.requirement_data.stat) }}
              <span v-if="getRequirementCount(req.requirement_data) > 1">
                (x{{ getRequirementCount(req.requirement_data) }})
              </span>
            </template>
                  <template v-else-if="req.requirement_type === 'room' && req.requirement_data">
                    Build {{ getRequirementCount(req.requirement_data) || 1 }} {{ roomDisplayName(req.requirement_data) }}
            </template>
            <template v-else-if="req.requirement_type === 'dweller_count' && req.requirement_data">
              Reach {{ getRequirementCount(req.requirement_data) }} dwellers
            </template>
            <template
              v-else-if="req.requirement_type === 'quest_completed' && req.requirement_data"
            >
              Complete: {{ questRequirementName(req.requirement_data) }}
            </template>
            <template v-else>
              {{ req.requirement_type }}
            </template>
          </span>
        </li>
      </ul>
    </div>

    <!-- Rewards -->
    <div class="quest-section">
      <div class="section-label">
        <Icon icon="mdi:treasure-chest" class="inline-icon" />
        REWARDS
      </div>
      <div v-if="quest.quest_rewards && quest.quest_rewards.length > 0" class="rewards-list">
        <div v-for="reward in quest.quest_rewards" :key="reward.id" class="reward-item">
          <Icon :icon="questRewardIcon(reward)" class="reward-icon" />
          <span class="reward-text">{{ formatQuestReward(reward) }}</span>
          <span v-if="reward.reward_chance < 1" class="reward-chance">
            ({{ Math.round(reward.reward_chance * 100) }}%)
          </span>
        </div>
      </div>
      <div v-else class="reward-fallback">
        <Icon icon="mdi:text" class="reward-icon" />
        <span>{{ quest.rewards }}</span>
      </div>
    </div>

    <!-- Party Members (for active/available quests) -->
    <div v-if="status !== 'completed' && (partyMembers?.length ?? 0) > 0" class="quest-section">
      <div class="section-label">
        <Icon icon="mdi:account-group" class="inline-icon" />
        PARTY
      </div>
      <div class="party-members">
        <div v-for="member in partyMembers ?? []" :key="member.id" class="party-member">
          <Icon icon="mdi:account" class="member-icon" />
          <span class="member-name">{{ member.first_name }} {{ member.last_name }}</span>
          <span class="member-level">Lv.{{ member.level || 1 }}</span>
        </div>
      </div>
    </div>

    <!-- Timed quest progress stays visible until its reward is claimed -->
    <div
      v-if="
        (status === 'active' && timeRemaining) ||
        (status === 'returning' && timeRemaining) ||
        (status === 'ready' && !isStateQuest)
      "
      class="quest-timer"
    >
      <div class="timer-header">
        <div class="timer-status">
          <Icon icon="mdi:clock-outline" class="timer-icon" />
          <span class="timer-label">
            {{ status === 'ready' ? 'Complete' : status === 'returning' ? 'Travelling Home' : 'Time Remaining' }}
          </span>
        </div>
        <span class="timer-value">{{ status === 'ready' ? 'Ready to claim' : timeRemaining }}</span>
      </div>
      <Progress :model-value="displayedQuestProgress" class="quest-progress-bar h-2" />
      <span class="timer-progress">{{ questProgressLabel }}</span>
    </div>

    <div v-if="status === 'available' && quest.duration_minutes && !isStateQuest" class="quest-duration">
      <Icon icon="mdi:clock-outline" class="duration-icon" />
      <span>Duration: {{ quest.duration_minutes }} min</span>
      <span v-if="!hasParty && !isStateQuest" class="duration-hint">(Assign party to start)</span>
    </div>

    </div>

    <div>
      <Button
        class="quest-action-btn"
        :variant="status === 'completed' ? 'secondary' : 'default'"
        :disabled="isButtonDisabled"
        @click="handleAction"
      >
        <Icon
          :icon="
            status === 'completed'
              ? 'mdi:eye'
              : status === 'ready'
                ? 'mdi:treasure-chest'
              : status === 'returning'
                ? 'mdi:home-import-outline'
              : status === 'active'
                ? 'mdi:progress-clock'
                : isStateQuest
                  ? 'mdi:clipboard-check'
                : hasParty
                  ? 'mdi:play'
                  : 'mdi:account-plus'
          "
          class="btn-icon"
        />
        {{ actionButtonText }}
      </Button>
    </div>
  </Card>
</template>

<style scoped>
.quest-card {
  background: var(--color-surface-warm-dark);
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

.completed-quest {
  opacity: 0.75;
  background: var(--color-surface-warm-dark);
}

.completed-quest::before {
  background: var(--color-quest-muted);
}

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
  margin: 0;
}

.quest-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  justify-content: flex-end;
}

.type-badge,
.category-badge,
.chain-badge,
.locked-badge {
  font-size: 0.7rem;
  font-weight: bold;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.locked-badge {
  border-color: var(--color-quest-locked) !important;
  color: var(--color-quest-locked) !important;
}

.quest-description {
  font-size: 0.9rem;
  color: var(--color-theme-primary);
  opacity: 0.85;
  margin-bottom: 12px;
  line-height: 1.5;
}

.quest-divider {
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--color-theme-primary), transparent);
  margin: 12px 0;
  opacity: 0.3;
}

.quest-section {
  margin-bottom: 12px;
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

.prerequisites-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.prerequisite-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  font-size: 0.9rem;
}

.prerequisite-item.met {
  color: var(--color-theme-primary);
}

.prerequisite-item.unmet {
  color: var(--color-quest-muted);
}

.prerequisite-icon {
  font-size: 1rem;
}

.prerequisite-item.met .prerequisite-icon {
  color: var(--color-theme-primary);
}

.prerequisite-item.unmet .prerequisite-icon {
  color: var(--color-quest-locked);
}

.rewards-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.reward-item,
.reward-fallback {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  font-size: 0.9rem;
  color: var(--color-theme-primary);
}

.reward-icon {
  color: var(--color-theme-accent);
}

.reward-chance {
  font-size: 0.8rem;
  opacity: 0.7;
}

.quest-action-btn {
  width: 100%;
}

.inline-icon {
  display: inline;
  vertical-align: middle;
}

.btn-icon {
  margin-right: 8px;
}

.party-members {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.party-member {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 4px;
  font-size: 0.85rem;
}

.member-icon {
  color: var(--color-theme-accent);
}

.member-name {
  flex: 1;
  color: var(--color-theme-primary);
  font-weight: bold;
}

.member-level {
  color: var(--color-theme-accent);
  font-size: 0.8rem;
}

.quest-timer {
  display: grid;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid color-mix(in srgb, var(--color-theme-primary) 25%, transparent);
  margin-top: 12px;
}

.timer-header,
.timer-status {
  display: flex;
  align-items: center;
}

.timer-header {
  justify-content: space-between;
  gap: 12px;
}

.timer-status {
  gap: 8px;
}

.quest-progress-bar {
  width: 100%;
}

.timer-progress {
  justify-self: end;
  color: var(--color-theme-primary);
  font-size: 0.7rem;
  letter-spacing: 0.08em;
  opacity: 0.75;
  text-transform: uppercase;
}

.timer-icon {
  font-size: 1.2rem;
  color: var(--color-theme-accent);
}

.timer-label {
  color: var(--color-theme-primary);
  font-size: 0.85rem;
}

.timer-value {
  font-weight: bold;
  font-size: 1.1rem;
  color: var(--color-theme-accent);
  font-family: 'Courier New', monospace;
}

.quest-duration {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 4px;
  margin-top: 12px;
  font-size: 0.85rem;
  color: var(--color-theme-primary);
}

.duration-icon {
  color: var(--color-theme-accent);
}

.duration-hint {
  color: var(--color-theme-primary);
  opacity: 0.6;
  font-size: 0.8rem;
  margin-left: auto;
}

/* Locked quest info styling */
.locked-info {
  background: rgba(255, 102, 0, 0.1);
  border: 1px solid var(--color-quest-locked);
  border-radius: 6px;
  padding: 12px;
  margin: 12px 0;
}

.locked-info .section-label {
  color: var(--color-quest-locked);
  font-size: 0.75rem;
  font-weight: bold;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 4px;
}

.locked-message {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--color-theme-primary);
  font-size: 0.9rem;
}

.locked-icon {
  color: var(--color-quest-locked);
  font-size: 1.1rem;
}
</style>
