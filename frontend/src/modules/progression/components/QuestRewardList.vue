<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { formatQuestReward, questRewardIcon } from '../models/quest'
import type { QuestReward } from '../models/quest'

withDefaults(
  defineProps<{ rewards: QuestReward[], fallbackText?: string }>(),
  { fallbackText: '' }
)
</script>

<template>
  <div class="quest-section">
    <div class="section-label">
      <Icon icon="mdi:treasure-chest" class="inline-icon" />
      REWARDS
    </div>
    <div v-if="rewards.length > 0" class="rewards-list">
      <div v-for="reward in rewards" :key="reward.id" class="reward-item">
        <Icon :icon="questRewardIcon(reward)" class="reward-icon" />
        <span class="reward-text">{{ formatQuestReward(reward) }}</span>
        <span v-if="reward.reward_chance < 1" class="reward-chance">
          ({{ Math.round(reward.reward_chance * 100) }}%)
        </span>
      </div>
    </div>
    <div v-else-if="fallbackText" class="reward-fallback">
      <Icon icon="mdi:text" class="reward-icon" />
      <span>{{ fallbackText }}</span>
    </div>
  </div>
</template>

<style scoped>
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

.inline-icon {
  display: inline;
  vertical-align: middle;
}
</style>
