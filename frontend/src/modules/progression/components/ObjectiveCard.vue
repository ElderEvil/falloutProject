<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import type { Objective } from '../models/objective'
import { isObjectiveClaimable } from '../models/objective'
import { Badge } from '@/core/components/ui/badge'
import { Button } from '@/core/components/ui/button'
import { Progress } from '@/core/components/ui/progress'
import { capitalize } from '@/core/utils/format'
import ProgressionCard from './ProgressionCard.vue'

interface Props {
  objective: Objective
  claiming?: boolean
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
  if (props.objective.target_entity?.production_only) return 'mdi:factory'
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

const categoryLabel = computed(() => capitalize(props.objective.category))

const canClaim = computed(() => isObjectiveClaimable(props.objective))
</script>

<template>
  <ProgressionCard
    class="objective-card"
    :title="objective.challenge"
    :description="objective.description"
    :completed="objective.is_completed"
  >
    <template #leading>
      <div class="objective-icon-wrapper">
        <Icon :icon="objectiveIcon" class="objective-icon" />
      </div>
    </template>

    <template #badges>
      <Badge variant="outline" class="category-badge">{{ categoryLabel }}</Badge>
    </template>

    <p v-if="objective.target_entity?.production_only" class="objective-note">
      Production counts even when storage is full.
    </p>
    <p v-else-if="objective.target_entity?.distinct_dwellers" class="objective-note">
      Each dweller counts once for this objective.
    </p>

    <!-- Progress Section -->
    <div class="progress-section">
      <div class="progress-header">
        <span class="progress-label">Progress</span>
        <span class="progress-values">{{ objective.progress }} / {{ objective.total }}</span>
      </div>
      <!-- @vue-ignore -->
      <Progress
        :model-value="progressPercent"
        aria-label="Objective progress"
        class="objective-progress-bar h-2"
      />
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
    <template #action>
      <Button
        v-if="canClaim"
        class="claim-btn"
        variant="default"
        :disabled="claiming"
        @click="emit('claim', objective.id)"
      >
        <Icon icon="mdi:gift-open" class="btn-icon" />
        Claim Reward
      </Button>
    </template>
  </ProgressionCard>
</template>

<style scoped>
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

.category-badge {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.objective-note {
  font-size: 0.9rem;
  color: var(--color-theme-primary);
  opacity: 0.85;
  line-height: 1.5;
  margin: 0 0 12px;
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

.objective-progress-bar {
  margin-bottom: 4px;
}

.progress-percent {
  text-align: right;
  font-size: 0.8rem;
  color: var(--color-theme-primary);
  opacity: 0.8;
}

.reward-section {
  background: var(--color-surface-raised);
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
}

.btn-icon {
  margin-right: 8px;
}
</style>
