<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import RewardsModalShell from '@/core/components/common/RewardsModalShell.vue'
import RewardCard from '@/core/components/common/RewardCard.vue'
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

const ITEM_META: Record<string, { icon: string; label: string }> = {
  weapon: { icon: 'mdi:sword-cross', label: 'Weapon' },
  outfit: { icon: 'mdi:tshirt-crew', label: 'Outfit' },
  junk: { icon: 'mdi:cog', label: 'Junk' },
  pet: { icon: 'mdi:paw', label: 'Pet' },
  consumable: { icon: 'mdi:bottle-tonic', label: 'Consumable' },
  lunchbox: { icon: 'mdi:gift', label: 'Lunchbox' },
}

const RESOURCE_META: Record<string, { icon: string; label: string }> = {
  power: { icon: 'mdi:flash', label: 'Power' },
  food: { icon: 'mdi:food-apple', label: 'Food' },
  water: { icon: 'mdi:water', label: 'Water' },
}

const rewards = computed(() => props.quest?.quest_rewards ?? [])

const rewardLabel = (reward: QuestReward): string => {
  const data = reward.reward_data as Record<string, unknown>
  const qtyRaw = (data.quantity ?? data.amount) as unknown
  const qtyNum = typeof qtyRaw === 'number' ? qtyRaw : Number(qtyRaw ?? 0)
  const qtyPrefix = qtyNum > 1 ? `${qtyNum}x ` : ''
  if (reward.reward_type === 'item') return `${qtyPrefix}${String(data.item_name || reward.item_data?.name || 'Item')}`
  if (reward.reward_type === 'dweller') return String((data.template_id as string) || (data.name as string) || 'New Dweller').replaceAll('-', ' ')
  return String(data.amount ?? qtyRaw ?? '—')
}

const inferItemCategory = (reward: QuestReward): string => {
  const explicit = String(reward.item_data?.item_type ?? reward.reward_data.item_type ?? '').toLowerCase()
  return explicit && ITEM_META[explicit] ? explicit : ''
}

const rewardMeta = (reward: QuestReward): { icon: string; label: string } => {
  const base = REWARD_META[reward.reward_type] ?? { icon: 'mdi:gift', label: 'Reward' }
  const data = reward.reward_data

  if (reward.reward_type === 'item') {
    const category = inferItemCategory(reward)
    return ITEM_META[category] ?? base
  }

  if (reward.reward_type === 'resource') {
    const resourceType = String(data.resource_type ?? '')
    return RESOURCE_META[resourceType] ?? base
  }

  return base
}
</script>

<template>
  <RewardsModalShell
    :show="show && !!quest"
    title="Quest Complete!"
    header-icon="mdi:treasure-chest"
    max-width="600px"
    @close="emit('close')"
  >
    <template #default>
      <div v-if="quest" class="quest-name">
        <Icon icon="mdi:flag-checkered" class="quest-name-icon" />
        {{ quest.title }} has returned. Confirm delivery to your vault.
      </div>

      <div v-if="rewards.length > 0" class="rewards-grid">
        <RewardCard
          v-for="reward in rewards"
          :key="reward.id"
          :icon="rewardMeta(reward).icon"
          :label="rewardMeta(reward).label"
          :value="rewardLabel(reward)"
        />
      </div>

      <div v-else class="no-items">
        <Icon icon="mdi:package-variant-closed" class="no-items-icon" />
        <p>No rewards listed for this quest</p>
      </div>
    </template>

    <template #footer>
      <button class="cancel-btn" @click="emit('close')">Review Later</button>
      <button class="collect-btn" @click="emit('confirm')">
        <Icon icon="mdi:check-bold" class="mr-2" />
        Confirm & Claim
      </button>
    </template>
  </RewardsModalShell>
</template>

<style scoped>
.quest-name {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  font-size: 1.1rem;
  color: var(--color-theme-primary);
  text-shadow: 0 0 6px var(--color-theme-glow);
  margin-bottom: 1.5rem;
}

.quest-name-icon {
  width: 1.5rem;
  height: 1.5rem;
  flex-shrink: 0;
  color: var(--color-theme-accent);
  filter: drop-shadow(0 0 4px var(--color-theme-glow));
}

.rewards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
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
