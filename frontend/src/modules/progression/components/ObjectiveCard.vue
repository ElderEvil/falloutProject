<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import type { Objective } from '../models/objective'
import { UCard, UBadge } from '@/core/components/ui'

interface Props {
  objective: Objective
}

const props = defineProps<Props>()

const emit = defineEmits<{
  claim: [objectiveId: string]
}>()

// Calculate progress percentage
const progressPercent = computed(() => {
  if (props.objective.total === 0) return 0
  return Math.min(100, Math.round((props.objective.progress / props.objective.total) * 100))
})

// Determine objective icon based on challenge text
const objectiveIcon = computed(() => {
  const challenge = props.objective.challenge.toLowerCase()
  if (challenge.includes('cap') || challenge.includes('collect')) return 'mdi:cash'
  if (challenge.includes('dweller')) return 'mdi:account-group'
  if (challenge.includes('room') || challenge.includes('build')) return 'mdi:home-group'
  if (challenge.includes('train')) return 'mdi:dumbbell'
  if (challenge.includes('explore')) return 'mdi:compass'
  if (challenge.includes('rush')) return 'mdi:lightning-bolt'
  if (challenge.includes('equip')) return 'mdi:tshirt-crew'
  return 'mdi:target'
})

// Determine objective category
const category = computed(() => {
  const challenge = props.objective.challenge.toLowerCase()
  if (challenge.includes('daily')) return 'daily'
  if (challenge.includes('weekly')) return 'weekly'
  return 'achievement'
})

const categoryLabel = computed(() => {
  return category.value.charAt(0).toUpperCase() + category.value.slice(1)
})

const isCompleted = computed(() => {
  return props.objective.is_completed || props.objective.progress >= props.objective.total
})

const canClaim = computed(() => {
  return isCompleted.value && !props.objective.is_completed
})
</script>

<template>
  <UCard class="objective-card" :class="{ 'completed-card': isCompleted }">
    <!-- Header with icon and category -->
    <div class="objective-header">
      <div class="objective-icon-wrapper">
        <Icon :icon="objectiveIcon" class="objective-icon" />
      </div>
      <div class="objective-info">
        <h3 class="objective-title">{{ objective.challenge }}</h3>
        <UBadge
          :variant="
            category === 'daily' ? 'primary' : category === 'weekly' ? 'secondary' : 'outline'
          "
          class="category-badge"
        >
          {{ categoryLabel }}
        </UBadge>
      </div>
    </div>

    <!-- Progress Section -->
    <div class="progress-section">
      <div class="progress-header">
        <span class="progress-label">Progress</span>
        <span class="progress-values">{{ objective.progress }} / {{ objective.total }}</span>
      </div>
      <div class="progress-bar-container">
        <div
          class="progress-bar"
          :style="{ width: `${progressPercent}%` }"
          :class="{ 'progress-complete': isCompleted }"
        ></div>
      </div>
      <div class="progress-percent">{{ progressPercent }}%</div>
    </div>

    <!-- Reward Section -->
    <div class="reward-section">
      <div class="reward-label">
        <Icon icon="mdi:gift" class="reward-icon" />
        Reward
      </div>
      <div class="reward-value">{{ objective.reward }}</div>
    </div>

    <!-- Claim Button (if completed but not claimed) -->
    <button v-if="canClaim" class="claim-btn" @click="emit('claim', objective.id)">
      <Icon icon="mdi:gift-open" class="btn-icon" />
      Claim Reward
    </button>

    <!-- Completed Stamp -->
    <div v-else-if="isCompleted" class="completed-stamp">
      <Icon icon="mdi:check-circle" class="stamp-icon" />
      Completed
    </div>
  </UCard>
</template>

<style scoped>
.objective-card {
  background: linear-gradient(135deg, #1a1a1a 0%, #2a2a2a 100%);
  border: 2px solid var(--color-theme-primary);
  border-radius: 6px;
  padding: 16px;
  transition: all 0.2s;
  position: relative;
  overflow: hidden;
}

.objective-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: var(--color-theme-primary);
  box-shadow: 0 0 8px var(--color-theme-glow);
}

.objective-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px var(--color-theme-glow);
}

.completed-card {
  border-color: #666666;
  opacity: 0.9;
  background: linear-gradient(135deg, #1a1a1a 0%, #252525 100%);
}

.completed-card::before {
  background: #00ff00;
}

.objective-header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 16px;
}

.objective-icon-wrapper {
  width: 48px;
  height: 48px;
  background: var(--color-theme-glow);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.objective-icon {
  font-size: 24px;
  color: var(--color-theme-primary);
}

.objective-info {
  flex: 1;
}

.objective-title {
  font-size: 1rem;
  font-weight: bold;
  color: var(--color-theme-primary);
  margin: 0 0 8px 0;
  line-height: 1.3;
}

.category-badge {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.progress-section {
  margin-bottom: 16px;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 0.85rem;
}

.progress-label {
  color: var(--color-theme-accent);
  font-weight: bold;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.progress-values {
  color: var(--color-theme-primary);
  font-weight: bold;
}

.progress-bar-container {
  height: 8px;
  background: rgba(0, 0, 0, 0.5);
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 4px;
}

.progress-bar {
  height: 100%;
  background: linear-gradient(90deg, var(--color-theme-primary), var(--color-theme-accent));
  transition: width 0.3s ease;
  border-radius: 4px;
}

.progress-complete {
  background: linear-gradient(90deg, #00ff00, #00cc00);
}

.progress-percent {
  text-align: right;
  font-size: 0.8rem;
  color: var(--color-theme-primary);
  opacity: 0.8;
}

.reward-section {
  background: rgba(0, 0, 0, 0.3);
  padding: 12px;
  border-radius: 4px;
  border-left: 3px solid var(--color-theme-accent);
}

.reward-label {
  font-size: 0.75rem;
  color: var(--color-theme-accent);
  font-weight: bold;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 4px;
}

.reward-icon {
  font-size: 14px;
}

.reward-value {
  font-size: 0.9rem;
  color: var(--color-theme-primary);
  font-weight: bold;
}

.claim-btn {
  width: 100%;
  margin-top: 12px;
  padding: 10px 16px;
  background: var(--color-theme-accent);
  color: #000000;
  border: none;
  border-radius: 4px;
  font-weight: bold;
  font-size: 0.9rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.claim-btn:hover {
  background: var(--color-theme-primary);
  box-shadow: 0 0 15px var(--color-theme-glow);
  transform: translateY(-1px);
}

.completed-stamp {
  margin-top: 12px;
  text-align: center;
  padding: 8px;
  background: rgba(0, 255, 0, 0.1);
  border: 2px dashed #00ff00;
  border-radius: 4px;
  color: #00ff00;
  font-weight: bold;
  font-size: 0.9rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.stamp-icon {
  font-size: 1.2rem;
}

.btn-icon {
  font-size: 1.1rem;
}
</style>
