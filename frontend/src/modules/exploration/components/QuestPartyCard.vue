<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Icon } from '@iconify/vue'
import type { VaultQuest } from '@/modules/progression/models/quest'
import type { QuestPartyMember } from '@/modules/progression/models/quest'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'

interface Props {
  quest: VaultQuest
  partyMembers: DwellerShort[]
  selected?: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  select: []
  complete: [questId: string]
}>()

const route = useRoute()

const vaultId = computed(() => route.params.id as string)

const partyNames = computed(() => {
  return props.partyMembers.map((m) => `${m.first_name} ${m.last_name}`).join(', ')
})

const progressPercentage = computed(() => {
  if (!props.quest.started_at || !props.quest.duration_minutes) return 0

  const now = Date.now()
  const startStr = props.quest.started_at.endsWith('Z')
    ? props.quest.started_at
    : props.quest.started_at.replace(' ', 'T') + 'Z'
  const start = new Date(startStr).getTime()
  const duration = props.quest.duration_minutes * 60 * 1000
  const elapsed = now - start

  return Math.min(100, (elapsed / duration) * 100)
})

const timeRemaining = computed(() => {
  const progress = progressPercentage.value
  if (progress >= 100) return 'Complete!'

  const totalDuration = (props.quest.duration_minutes || 0) * 60
  const remaining = totalDuration * (1 - progress / 100)

  const hours = Math.floor(remaining / 3600)
  const minutes = Math.floor((remaining % 3600) / 60)

  if (hours > 0) {
    return `${hours}h ${minutes}m remaining`
  }
  return `${minutes}m remaining`
})

const statusColor = computed(() => {
  const progress = progressPercentage.value
  if (progress >= 100) return '#FFD700'
  if (progress >= 75) return 'var(--color-theme-accent)'
  return 'var(--color-theme-primary)'
})
</script>

<template>
  <div class="quest-party-card" :class="{ selected }" @click="emit('select')">
    <div class="card-header">
      <div class="quest-info">
        <Icon icon="mdi:sword-cross" class="quest-icon" />
        <div>
          <div class="quest-title">{{ quest.title }}</div>
          <div class="quest-duration">{{ quest.duration_minutes }}m quest</div>
        </div>
      </div>
      <div v-if="selected" class="selected-indicator">
        <Icon icon="mdi:check-circle" />
      </div>
    </div>

    <div class="progress-section">
      <div class="progress-bar-container">
        <div
          class="progress-bar"
          :style="{
            width: `${progressPercentage}%`,
            background: statusColor,
          }"
        ></div>
      </div>
      <div class="progress-info">
        <span class="progress-percentage">{{ Math.round(progressPercentage) }}%</span>
        <span class="progress-time">{{ timeRemaining }}</span>
      </div>
    </div>

    <div class="party-section">
      <div class="party-header">
        <Icon icon="mdi:account-group" class="party-icon" />
        <span class="party-label">Party ({{ partyMembers.length }}/3)</span>
      </div>
      <div class="party-members">
        <div v-for="member in partyMembers" :key="member.id" class="party-member">
          <Icon icon="mdi:account" class="member-icon" />
          <span class="member-name">{{ member.first_name }} {{ member.last_name }}</span>
        </div>
      </div>
    </div>

    <div class="card-actions">
      <button
        v-if="progressPercentage >= 100"
        @click.stop="emit('complete', quest.id)"
        class="action-btn complete-btn"
      >
        <Icon icon="mdi:check-circle" />
        Complete Quest
      </button>
    </div>
  </div>
</template>

<style scoped>
.quest-party-card {
  background: rgba(0, 0, 0, 0.7);
  border: 2px solid rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.3);
  border-radius: 8px;
  padding: 1.25rem;
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.quest-party-card:hover {
  border-color: var(--color-theme-primary);
  background: rgba(0, 0, 0, 0.85);
  box-shadow: 0 0 20px var(--color-theme-glow);
  transform: translateY(-2px);
}

.quest-party-card.selected {
  border-color: var(--color-theme-primary);
  border-width: 3px;
  background: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.05);
  box-shadow: 0 0 30px var(--color-theme-glow);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.quest-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.quest-icon {
  width: 2.5rem;
  height: 2.5rem;
  color: var(--color-theme-secondary);
  filter: drop-shadow(0 0 6px var(--color-theme-glow));
}

.quest-title {
  font-size: 1.125rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 6px var(--color-theme-glow);
}

.quest-duration {
  font-size: 0.75rem;
  color: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.7);
}

.selected-indicator {
  color: var(--color-theme-primary);
  font-size: 1.5rem;
}

.progress-section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.progress-bar-container {
  width: 100%;
  height: 12px;
  background: rgba(0, 0, 0, 0.5);
  border: 1px solid rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.3);
  border-radius: 6px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  border-radius: 6px;
  transition:
    width 0.5s ease,
    background 0.3s ease;
  box-shadow: 0 0 10px currentColor;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.75rem;
}

.progress-percentage {
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 4px var(--color-theme-glow);
}

.progress-time {
  color: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.7);
}

.party-section {
  padding: 0.75rem;
  background: rgba(0, 0, 0, 0.4);
  border: 1px solid rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.2);
  border-radius: 4px;
}

.party-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.party-icon {
  width: 1.25rem;
  height: 1.25rem;
  color: var(--color-theme-secondary);
}

.party-label {
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.party-members {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.party-member {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.9);
}

.member-icon {
  width: 1rem;
  height: 1rem;
  color: var(--color-theme-primary);
}

.member-name {
  font-weight: 600;
}

.card-actions {
  display: flex;
  gap: 0.5rem;
  padding-top: 0.5rem;
  border-top: 1px solid rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.2);
}

.action-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.75rem;
  border-radius: 4px;
  font-size: 0.875rem;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s ease;
  font-family: 'Courier New', monospace;
  border: 2px solid;
}

.complete-btn {
  background: rgba(255, 215, 0, 0.1);
  border-color: #ffd700;
  color: #ffd700;
}

.complete-btn:hover {
  background: rgba(255, 215, 0, 0.2);
  box-shadow: 0 0 15px rgba(255, 215, 0, 0.4);
  transform: scale(1.02);
}
</style>
