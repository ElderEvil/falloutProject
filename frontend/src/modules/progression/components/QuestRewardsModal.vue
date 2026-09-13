<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { UButton, UModal } from '@/core/components/ui'
import RewardCard from '@/core/components/common/RewardCard.vue'
import TerminalModalActions from '@/core/components/common/TerminalModalActions.vue'
import type { components } from '@/core/types/api.generated'
import type { QuestReward, VaultQuest } from '../models/quest'
import { describeGrantedReward } from '../models/quest'

type GrantedReward = components['schemas']['QuestCompleteResponse']['granted_rewards'][number]

interface Props {
  quest: VaultQuest | null
  show: boolean
  grantedRewards?: GrantedReward[] | null
}

const props = withDefaults(defineProps<Props>(), { grantedRewards: null })

const emit = defineEmits<{
  close: []
  confirm: []
}>()

const REWARD_META: Record<QuestReward['reward_type'], { icon: string, label: string }> = {
  caps: { icon: 'mdi:currency-usd', label: 'Bottle Caps' },
  item: { icon: 'mdi:package-variant', label: 'Item' },
  dweller: { icon: 'mdi:account-plus', label: 'New Dweller' },
  resource: { icon: 'mdi:database', label: 'Resource' },
  experience: { icon: 'mdi:star', label: 'Experience' },
  stimpak: { icon: 'mdi:medical-bag', label: 'Stimpak' },
  radaway: { icon: 'mdi:radiation', label: 'RadAway' },
  lunchbox: { icon: 'mdi:gift', label: 'Lunchbox' },
}

const ITEM_META: Record<string, { icon: string, label: string }> = {
  weapon: { icon: 'mdi:sword-cross', label: 'Weapon' },
  outfit: { icon: 'mdi:tshirt-crew', label: 'Outfit' },
  junk: { icon: 'mdi:cog', label: 'Junk' },
  pet: { icon: 'mdi:paw', label: 'Pet' },
  consumable: { icon: 'mdi:bottle-tonic', label: 'Consumable' },
  lunchbox: { icon: 'mdi:gift', label: 'Lunchbox' },
}

const RESOURCE_META: Record<string, { icon: string, label: string }> = {
  power: { icon: 'mdi:flash', label: 'Power' },
  food: { icon: 'mdi:food-apple', label: 'Food' },
  water: { icon: 'mdi:water', label: 'Water' },
}

const isGrantedMode = computed(() => props.grantedRewards !== null)

const rewards = computed(() => props.quest?.quest_rewards ?? [])

const chanceSuffix = (reward: QuestReward): string => {
  if (reward.reward_chance >= 1) return ''
  return ` · ${Math.round(reward.reward_chance * 100)}% chance`
}

const rewardLabel = (reward: QuestReward): string => {
  const data = reward.reward_data as Record<string, unknown>
  const qtyRaw = (data.quantity ?? data.amount) as unknown
  const qtyNum = typeof qtyRaw === 'number' ? qtyRaw : Number(qtyRaw ?? 0)
  const qtyPrefix = qtyNum > 1 ? `${qtyNum}x ` : ''
  if (reward.reward_type === 'item') return `${qtyPrefix}${String(data.item_name || reward.item_data?.name || 'Item')}${chanceSuffix(reward)}`
  if (reward.reward_type === 'dweller') return `${String((data.template_id as string) || (data.name as string) || 'New Dweller').replaceAll('-', ' ')}${chanceSuffix(reward)}`
  return `${String(data.amount ?? qtyRaw ?? '—')}${chanceSuffix(reward)}`
}

const inferItemCategory = (reward: QuestReward): string => {
  const explicit = String(reward.item_data?.item_type ?? reward.reward_data.item_type ?? '').toLowerCase()
  return explicit && ITEM_META[explicit] ? explicit : ''
}

const rewardMeta = (reward: QuestReward): { icon: string, label: string } => {
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

interface GrantedCard {
  icon: string
  label: string
  value: string
}

const grantedCards = computed<GrantedCard[]>(() => (props.grantedRewards ?? []).map(describeGrantedReward))

const hasUnopenedLunchbox = computed(() => (props.grantedRewards ?? []).some(
  reward => reward.reward_type === 'item' && reward.item_type === 'lunchbox',
))
</script>

<template>
  <UModal
    :model-value="show && !!quest"
    :title="isGrantedMode ? 'Delivery Confirmed!' : 'Quest Complete!'"
    size="wide"
    @close="emit('close')"
  >
    <template #header="{ titleId }">
      <div class="quest-complete-header flex items-center gap-3">
        <Icon icon="mdi:treasure-chest" class="h-8 w-8 text-theme-primary terminal-glow" />
        <h2 :id="titleId" class="text-2xl font-bold text-theme-primary terminal-glow">{{ isGrantedMode ? 'Delivery Confirmed!' : 'Quest Complete!' }}</h2>
      </div>
    </template>

    <div v-if="quest && !isGrantedMode" class="quest-return-banner mb-6 flex items-center gap-3 rounded-md border border-theme-primary/30 bg-theme-primary/10 p-4 text-lg text-theme-primary">
      <Icon icon="mdi:flag-checkered" class="h-6 w-6 shrink-0 text-theme-accent" />
      {{ quest.title }} has returned. Confirm delivery to your vault.
    </div>

    <div v-if="quest && isGrantedMode" class="quest-return-banner mb-6 flex items-center gap-3 rounded-md border border-theme-primary/30 bg-theme-primary/10 p-4 text-lg text-theme-primary">
      <Icon icon="mdi:check-bold" class="h-6 w-6 shrink-0 text-theme-accent" />
      {{ quest.title }} delivered. This is what arrived in your vault.
    </div>

    <div v-if="isGrantedMode && grantedCards.length > 0" class="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <RewardCard
        v-for="(card, index) in grantedCards"
        :key="index"
        :icon="card.icon"
        :label="card.label"
        :value="card.value"
      />
    </div>

    <div v-else-if="!isGrantedMode && rewards.length > 0" class="grid grid-cols-1 gap-4 sm:grid-cols-2">
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

    <div v-if="isGrantedMode && hasUnopenedLunchbox" class="mt-4 flex items-center gap-3 rounded-md border border-theme-accent/30 bg-theme-accent/10 p-4 text-theme-accent">
      <Icon icon="mdi:gift" class="h-6 w-6 shrink-0" />
      Contains an unopened lunchbox — open it from the Storage supplies tab.
    </div>

    <template #footer>
      <TerminalModalActions
        v-if="!isGrantedMode"
        cancel-label="Review Later"
        confirm-label="Confirm & Claim"
        confirm-icon="mdi:check-bold"
        alignment="between"
        @cancel="emit('close')"
        @confirm="emit('confirm')"
      />
      <div v-else class="flex w-full justify-end">
        <UButton variant="primary" @click="emit('close')">Done</UButton>
      </div>
    </template>
  </UModal>
</template>
