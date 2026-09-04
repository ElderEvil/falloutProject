<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { UModal } from '@/core/components/ui'
import RewardCard from '@/core/components/common/RewardCard.vue'
import TerminalModalActions from '@/core/components/common/TerminalModalActions.vue'
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
  <UModal
    :model-value="show && !!quest"
    title="Quest Complete!"
    size="wide"
    @close="emit('close')"
  >
    <template #header="{ titleId }">
      <div class="quest-complete-header flex items-center gap-3">
        <Icon icon="mdi:treasure-chest" class="h-8 w-8 text-theme-primary terminal-glow" />
        <h2 :id="titleId" class="text-2xl font-bold text-theme-primary terminal-glow">Quest Complete!</h2>
      </div>
    </template>

    <div v-if="quest" class="quest-return-banner mt-5 mb-6 flex items-center gap-3 rounded-md border border-theme-primary/30 bg-theme-primary/10 p-4 text-lg text-theme-primary">
      <Icon icon="mdi:flag-checkered" class="h-6 w-6 shrink-0 text-theme-accent" />
      {{ quest.title }} has returned. Confirm delivery to your vault.
    </div>

    <div v-if="rewards.length > 0" class="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <RewardCard
        v-for="reward in rewards"
        :key="reward.id"
        :icon="rewardMeta(reward).icon"
        :label="rewardMeta(reward).label"
        :value="rewardLabel(reward)"
      />
    </div>

    <div v-else class="flex flex-col items-center gap-3 p-8 text-theme-primary/60">
      <Icon icon="mdi:package-variant-closed" class="h-12 w-12" />
      <p>No rewards listed for this quest</p>
    </div>

    <template #footer>
      <TerminalModalActions
        cancel-label="Review Later"
        confirm-label="Confirm & Claim"
        confirm-icon="mdi:check-bold"
        alignment="between"
        @cancel="emit('close')"
        @confirm="emit('confirm')"
      />
    </template>
  </UModal>
</template>
