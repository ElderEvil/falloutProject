<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted, watch } from 'vue'
import { Icon } from '@iconify/vue'
import type { VaultQuest, QuestPartyMember } from '../models/quest'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import { UCard, UBadge, UButton } from '@/core/components/ui'
import { useQuestStore } from '@/stores/quest'

const questStore = useQuestStore()

interface Props {
  quest: VaultQuest
  vaultId: string
  status: 'available' | 'active' | 'completed' | 'locked'
  partyMembers?: DwellerShort[]
  isLocked?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  partyMembers: () => [],
  isLocked: false,
})

const emit = defineEmits<{
  start: [questId: string]
  complete: [questId: string]
  view: [questId: string]
  assignParty: [questId: string]
}>()

const timeRemaining = ref<string | null>(null)
let timerInterval: ReturnType<typeof setInterval> | null = null

const updateTimer = () => {
  if (!props.quest.started_at || !props.quest.duration_minutes) {
    timeRemaining.value = null
    return
  }

  const startTime = new Date(props.quest.started_at).getTime()
  const durationMs = props.quest.duration_minutes * 60 * 1000
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

const startTimer = () => {
  if (timerInterval) {
    clearInterval(timerInterval)
  }
  if (props.status === 'active' && props.quest.started_at && props.quest.duration_minutes) {
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
  () => [props.status, props.quest.started_at],
  () => {
    if (props.status === 'active' && props.quest.started_at && props.quest.duration_minutes) {
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

const hasParty = computed(() => {
  return props.partyMembers && props.partyMembers.length > 0
})
const isQuestReady = computed(() => hasParty.value)

// Type badge colors
const typeColors: Record<string, { bg: string; text: string; border: string }> = {
  main: { bg: '#ffb000', text: '#000000', border: '#ffb000' },
  side: { bg: '#c0c0c0', text: '#000000', border: '#c0c0c0' },
  daily: { bg: '#00d9ff', text: '#000000', border: '#00d9ff' },
  event: { bg: '#9b59b6', text: '#ffffff', border: '#9b59b6' },
  repeatable: { bg: '#00ff00', text: '#000000', border: '#00ff00' },
}

const typeColor = computed(() => {
  return typeColors[props.quest.quest_type] || typeColors.side
})

const typeLabel = computed(() => {
  const questType = props.quest.quest_type || 'side'
  return questType.charAt(0).toUpperCase() + questType.slice(1)
})

const isChainQuest = computed(() => {
  return props.quest.chain_id !== null
})

const chainPosition = computed(() => {
  if (!isChainQuest.value) return null
  return props.quest.chain_order > 0 ? `Quest ${props.quest.chain_order}` : 'Chain Quest'
})

// Get the previous quest name for locked quests
const previousQuestName = computed(() => {
  if (!props.quest.previous_quest_id) return null
  // Search in vaultQuests first, then fall back to all quests
  const previousQuest = questStore.vaultQuests.find((q) => q.id === props.quest.previous_quest_id)
    || questStore.quests.find((q) => q.id === props.quest.previous_quest_id)
  return previousQuest?.title || null
})

// Format reward details for display
const formatReward = (reward: { reward_type: string; reward_data: Record<string, unknown>; reward_chance: number }) => {
  const data = reward.reward_data || {}
  const type = reward.reward_type.toLowerCase()

  switch (type) {
    case 'caps':
      return `${data.amount || 0} Caps`
    case 'resource': {
      const resourceType = String(data.resource_type || 'resource')
      return `${data.amount || 0} ${resourceType.charAt(0).toUpperCase() + resourceType.slice(1)}`
    }
    case 'experience':
      return `${data.amount || 0} XP`
    case 'item': {
      const itemName = String(data.name || 'Unknown Item')
      const rarity = data.rarity ? ` (${String(data.rarity)})` : ''
      return `${itemName}${rarity}`
    }
    case 'dweller': {
      const name = String(data.first_name || data.name || 'New Dweller')
      const rarity = data.rarity ? ` (${String(data.rarity)})` : ''
      return `${name}${rarity}`
    }
    case 'stimpak': {
      const amt = Number(data.amount) || 1
      return `${amt} Stimpak${amt > 1 ? 's' : ''}`
    }
    case 'radaway': {
      const amt = Number(data.amount) || 1
      return `${amt} Radaway${amt > 1 ? 's' : ''}`
    }
    case 'lunchbox':
      return 'Lunchbox (3 items + 1 dweller)'
    default:
      return type.charAt(0).toUpperCase() + type.slice(1)
  }
}

// Get reward icon based on type
const getRewardIcon = (rewardType: string) => {
  switch (rewardType.toLowerCase()) {
    case 'caps':
      return 'mdi:currency-usd'
    case 'resource':
      return 'mdi:package-variant'
    case 'experience':
      return 'mdi:star'
    case 'item':
      return 'mdi:sword'
    case 'dweller':
      return 'mdi:account-plus'
    case 'stimpak':
      return 'mdi:medical-bag'
    case 'radaway':
      return 'mdi:pill'
    case 'lunchbox':
      return 'mdi:gift'
    default:
      return 'mdi:gift'
  }
}

const hasPrerequisites = computed(() => {
  return props.quest.quest_requirements && props.quest.quest_requirements.length > 0
})

const prerequisitesMet = computed(() => {
  if (!hasPrerequisites.value) return true
  // For now, assume prerequisites are met if quest is active or completed
  // In a real implementation, this would check actual vault state
  return props.status !== 'available'
})

const actionButtonText = computed(() => {
  if (props.isLocked) {
    return 'Locked'
  }
  switch (props.status) {
    case 'available':
      return 'Start Quest'
    case 'active':
      return timeRemaining.value ? 'In Progress' : 'Complete Quest'
    case 'completed':
      return 'View Details'
    default:
      return 'View'
  }
})

const cardBorderColor = computed(() => {
  if (props.isLocked) {
    return '#ff6600'
  }
  switch (props.status) {
    case 'active':
      return 'var(--color-theme-accent)'
    case 'completed':
      return '#666666'
    default:
      return typeColor.value.border
  }
})

const isButtonDisabled = computed(() => {
  return props.isLocked
})

const handleAction = () => {
  if (props.isLocked) {
    return // Don't do anything for locked quests
  }
  switch (props.status) {
    case 'available':
      if (hasParty.value) {
        emit('start', props.quest.id)
      } else {
        emit('assignParty', props.quest.id)
      }
      break
    case 'active':
      emit('complete', props.quest.id)
      break
    case 'completed':
      emit('view', props.quest.id)
      break
  }
}
</script>

<template>
  <UCard
    class="quest-card"
    :style="{ borderColor: cardBorderColor }"
    :class="{ 'completed-quest': status === 'completed' }"
  >
    <!-- Header -->
    <div class="quest-header">
      <h3 class="quest-title">{{ quest.title }}</h3>
      <div class="quest-badges">
        <UBadge
          :style="{ backgroundColor: typeColor.bg, color: typeColor.text }"
          class="type-badge"
        >
          {{ typeLabel }}
        </UBadge>
        <UBadge v-if="quest.quest_category" variant="secondary" class="category-badge">
          {{ quest.quest_category }}
        </UBadge>
        <UBadge v-if="isChainQuest" variant="outline" class="chain-badge">
          <Icon icon="mdi:link-variant" class="inline-icon" />
          {{ chainPosition }}
        </UBadge>
        <UBadge v-if="isLocked" variant="outline" class="locked-badge">
          <Icon icon="mdi:lock" class="inline-icon" />
          LOCKED
        </UBadge>
      </div>
    </div>

    <!-- Description -->
    <p class="quest-description">{{ quest.short_description }}</p>

    <!-- Previous Quest Info (for locked chain quests) -->
    <div v-if="isLocked && previousQuestName" class="quest-section locked-info">
      <div class="section-label">
        <Icon icon="mdi:lock-alert" class="inline-icon" />
        LOCKED
      </div>
      <div class="locked-message">
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
          :class="{ met: prerequisitesMet, unmet: !prerequisitesMet }"
        >
          <Icon
            :icon="prerequisitesMet ? 'mdi:check-circle' : 'mdi:lock'"
            class="prerequisite-icon"
          />
          <span class="prerequisite-text">
            <template v-if="req.requirement_type === 'level' && req.requirement_data">
              Requires Level {{ req.requirement_data.level || 1 }}+ dweller
              <span v-if="req.requirement_data.count > 1">(x{{ req.requirement_data.count }})</span>
            </template>
            <template v-else-if="req.requirement_type === 'item' && req.requirement_data">
              Requires {{ req.requirement_data.name || req.requirement_data.item_id }}
              <span v-if="req.requirement_data.count > 1">(x{{ req.requirement_data.count }})</span>
            </template>
            <template
              v-else-if="req.requirement_type === 'quest_completed' && req.requirement_data"
            >
              Complete: {{ req.requirement_data.quest_name || 'Previous quest' }}
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
          <Icon :icon="getRewardIcon(reward.reward_type)" class="reward-icon" />
          <span class="reward-text">{{ formatReward(reward) }}</span>
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
    <div v-if="status !== 'completed' && partyMembers.length > 0" class="quest-section">
      <div class="section-label">
        <Icon icon="mdi:account-group" class="inline-icon" />
        PARTY
      </div>
      <div class="party-members">
        <div v-for="member in partyMembers" :key="member.id" class="party-member">
          <Icon icon="mdi:account" class="member-icon" />
          <span class="member-name">{{ member.first_name }} {{ member.last_name }}</span>
          <span class="member-level">Lv.{{ member.level || 1 }}</span>
        </div>
      </div>
    </div>

    <!-- Timer (for active quests) -->
    <div v-if="status === 'active' && timeRemaining" class="quest-timer">
      <Icon icon="mdi:clock-outline" class="timer-icon" />
      <span class="timer-label">Time Remaining:</span>
      <span class="timer-value">{{ timeRemaining }}</span>
    </div>

    <!-- Duration Info (for available quests) -->
    <div v-if="status === 'available' && quest.duration_minutes" class="quest-duration">
      <Icon icon="mdi:clock-outline" class="duration-icon" />
      <span>Duration: {{ quest.duration_minutes }} min</span>
      <span v-if="!hasParty" class="duration-hint">(Assign party to start)</span>
    </div>

    <!-- Action Button -->
    <UButton
      class="quest-action-btn"
      :variant="status === 'completed' ? 'secondary' : 'primary'"
      :disabled="isButtonDisabled"
      @click="handleAction"
    >
      <Icon
        :icon="
          status === 'completed'
            ? 'mdi:eye'
            : status === 'active'
              ? 'mdi:progress-clock'
              : hasParty
                ? 'mdi:play'
                : 'mdi:account-plus'
        "
        class="btn-icon"
      />
      {{ actionButtonText }}
    </UButton>
  </UCard>
</template>

<style scoped>
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

.completed-quest {
  opacity: 0.75;
  background: linear-gradient(135deg, #1a1a1a 0%, #252525 100%);
}

.completed-quest::before {
  background: #666666;
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
  border-color: #ff6600 !important;
  color: #ff6600 !important;
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
  color: #666666;
}

.prerequisite-icon {
  font-size: 1rem;
}

.prerequisite-item.met .prerequisite-icon {
  color: #00ff00;
}

.prerequisite-item.unmet .prerequisite-icon {
  color: #ff6600;
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
  margin-top: 12px;
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
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  background: rgba(0, 217, 255, 0.1);
  border: 1px solid var(--color-theme-accent);
  border-radius: 6px;
  margin-top: 12px;
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
  border: 1px solid #ff6600;
  border-radius: 6px;
  padding: 12px;
  margin: 12px 0;
}

.locked-info .section-label {
  color: #ff6600;
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
  color: #ff6600;
  font-size: 1.1rem;
}
</style>
