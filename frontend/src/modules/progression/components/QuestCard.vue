<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import type { VaultQuest } from '../models/quest'
import { UCard, UBadge, UButton } from '@/core/components/ui'

interface Props {
  quest: VaultQuest
  vaultId: string
  status: 'available' | 'active' | 'completed'
}

const props = defineProps<Props>()

const emit = defineEmits<{
  start: [questId: string]
  complete: [questId: string]
  view: [questId: string]
}>()

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
  switch (props.status) {
    case 'available':
      return 'Start Quest'
    case 'active':
      return 'Complete Quest'
    case 'completed':
      return 'View Details'
    default:
      return 'View'
  }
})

const cardBorderColor = computed(() => {
  switch (props.status) {
    case 'active':
      return 'var(--color-theme-accent)'
    case 'completed':
      return '#666666'
    default:
      return typeColor.value.border
  }
})

const handleAction = () => {
  switch (props.status) {
    case 'available':
      emit('start', props.quest.id)
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
      </div>
    </div>

    <!-- Description -->
    <p class="quest-description">{{ quest.short_description }}</p>

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
          <span class="prerequisite-text">{{ req.requirement_type }}</span>
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
        <div
          v-for="reward in quest.quest_rewards"
          :key="reward.id"
          class="reward-item"
        >
          <Icon icon="mdi:gift" class="reward-icon" />
          <span class="reward-text">{{ reward.reward_type }}</span>
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

    <!-- Action Button -->
    <UButton
      class="quest-action-btn"
      :variant="status === 'completed' ? 'secondary' : 'primary'"
      :disabled="status === 'available' && !prerequisitesMet"
      @click="handleAction"
    >
      <Icon
        :icon="status === 'completed' ? 'mdi:eye' : status === 'active' ? 'mdi:check-bold' : 'mdi:play'"
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
.chain-badge {
  font-size: 0.7rem;
  font-weight: bold;
  letter-spacing: 0.1em;
  text-transform: uppercase;
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
</style>
