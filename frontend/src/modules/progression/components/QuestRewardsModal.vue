<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import type { QuestReward, VaultQuest } from '../models/quest'

interface Props {
  quest: VaultQuest | null
  show: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  close: []
  confirm: []
}>()

const REWARD_META: Record<QuestReward['reward_type'], { icon: string; label: string }> = {
  caps: { icon: 'mdi:currency-usd', label: 'Bottle Caps' },
  item: { icon: 'mdi:package-variant', label: 'Item' },
  dweller: { icon: 'mdi:account-plus', label: 'New Dweller' },
  resource: { icon: 'mdi:database', label: 'Resource' },
  experience: { icon: 'mdi:star', label: 'Experience' },
  stimpak: { icon: 'mdi:medical-bag', label: 'Stimpak' },
  radaway: { icon: 'mdi:radiation', label: 'RadAway' },
  lunchbox: { icon: 'mdi:gift', label: 'Lunchbox' },
}

const rewards = computed(() => props.quest?.quest_rewards ?? [])

const rewardLabel = (reward: QuestReward): string => {
  const data = reward.reward_data
  if (reward.reward_type === 'item') return String(data.item_name || reward.item_data?.name || 'Item')
  if (reward.reward_type === 'dweller') return String(data.template_id || data.name || 'New Dweller').replaceAll('-', ' ')
  return String(data.amount ?? '—')
}

const rewardMeta = (reward: QuestReward) => REWARD_META[reward.reward_type] ?? { icon: 'mdi:gift', label: 'Reward' }
</script>

<template>
  <Teleport to="body">
    <div v-if="show && quest" class="modal-overlay" @click="emit('close')">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <div class="header-title">
            <Icon icon="mdi:treasure-chest" class="header-icon" />
            <h2 class="title">Quest Complete!</h2>
          </div>
          <button class="close-btn" aria-label="Close" @click="emit('close')">
            <Icon icon="mdi:close" />
          </button>
        </div>

        <div class="modal-body">
          <div class="quest-name">
            <Icon icon="mdi:flag-checkered" class="mr-2" />
            {{ quest.title }} has returned. Confirm delivery to your vault.
          </div>

          <div v-if="rewards.length > 0" class="rewards-grid">
            <div v-for="reward in rewards" :key="reward.id" class="reward-card">
              <div class="reward-icon-container">
                <Icon :icon="rewardMeta(reward).icon" class="reward-icon" />
              </div>
              <div class="reward-details">
                <div class="reward-label">{{ rewardMeta(reward).label }}</div>
                <div class="reward-value">{{ rewardLabel(reward) }}</div>
              </div>
            </div>
          </div>

          <div v-else class="no-items">
            <Icon icon="mdi:package-variant-closed" class="no-items-icon" />
            <p>No rewards listed for this quest</p>
          </div>
        </div>

        <div class="modal-footer">
          <button class="cancel-btn" @click="emit('close')">Review Later</button>
          <button class="collect-btn" @click="emit('confirm')">
            <Icon icon="mdi:check-bold" class="mr-2" />
            Confirm & Claim
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
  backdrop-filter: blur(4px);
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.modal-content {
  background: var(--color-surface-dark);
  border: 2px solid var(--color-theme-primary);
  border-radius: 8px;
  width: 90%;
  max-width: 600px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 0 40px var(--color-theme-glow);
  animation: slideUp 0.3s ease;
}

@keyframes slideUp {
  from {
    transform: translateY(20px);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem;
  border-bottom: 2px solid color-mix(in srgb, var(--color-theme-primary) 30%, transparent);
}

.header-title {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.header-icon {
  width: 2rem;
  height: 2rem;
  color: var(--color-rarity-legendary);
  filter: drop-shadow(0 0 8px rgba(255, 215, 0, 0.6));
}

.title {
  font-size: 1.75rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 10px var(--color-theme-glow);
}

.close-btn {
  background: transparent;
  border: 2px solid color-mix(in srgb, var(--color-theme-primary) 50%, transparent);
  color: var(--color-theme-primary);
  padding: 0.5rem;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.25rem;
}

.close-btn:hover {
  background: color-mix(in srgb, var(--color-theme-primary) 30%, transparent);
  border-color: var(--color-theme-primary);
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
}

.quest-name {
  display: flex;
  align-items: center;
  font-size: 1.1rem;
  color: var(--color-theme-primary);
  text-shadow: 0 0 6px var(--color-theme-glow);
  margin-bottom: 1.5rem;
}

.rewards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
}

.reward-card {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem;
  border: 1px solid color-mix(in srgb, var(--color-theme-primary) 40%, transparent);
  border-radius: 6px;
  background: color-mix(in srgb, var(--color-surface) 80%, transparent);
}

.reward-icon-container {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 3rem;
  height: 3rem;
  border-radius: 50%;
  border: 2px solid var(--color-theme-accent);
  background: color-mix(in srgb, var(--color-theme-secondary) 60%, transparent);
  flex-shrink: 0;
}

.reward-icon {
  width: 1.5rem;
  height: 1.5rem;
  color: var(--color-theme-accent);
}

.reward-details {
  min-width: 0;
}

.reward-label {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--color-theme-primary);
  opacity: 0.7;
}

.reward-value {
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 6px var(--color-theme-glow);
}

.no-items {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
  padding: 2rem;
  color: var(--color-theme-primary);
  opacity: 0.6;
}

.no-items-icon {
  width: 3rem;
  height: 3rem;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding: 1.25rem 1.5rem;
  border-top: 2px solid color-mix(in srgb, var(--color-theme-primary) 30%, transparent);
}

.cancel-btn {
  background: transparent;
  border: 2px solid color-mix(in srgb, var(--color-theme-primary) 50%, transparent);
  color: var(--color-theme-primary);
  padding: 0.6rem 1.25rem;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  transition: all 0.2s ease;
}

.cancel-btn:hover {
  background: color-mix(in srgb, var(--color-theme-primary) 15%, transparent);
}

.collect-btn {
  background: var(--color-theme-accent);
  border: 2px solid var(--color-theme-primary);
  color: var(--color-terminal-background);
  padding: 0.6rem 1.5rem;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  display: inline-flex;
  align-items: center;
  transition: all 0.2s ease;
}

.collect-btn:hover {
  background: var(--color-theme-primary);
  box-shadow: 0 0 15px var(--color-theme-glow);
}
</style>
