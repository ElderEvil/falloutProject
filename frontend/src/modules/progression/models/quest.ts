/**
 * Quest model
 *
 * Represents a quest/mission that can be assigned to a vault and completed for rewards.
 * Quests are only accessible when the Overseer's Office is built.
 */
import type { components } from '@/core/types/api.generated'

export type GrantedReward = components['schemas']['QuestCompleteResponse']['granted_rewards'][number]
export interface Quest {
  id: string
  title: string
  short_description: string
  long_description: string
  requirements: string
  rewards: string
  quest_type: QuestType
  quest_category: string | null
  chain_id: string | null
  chain_order: number
  previous_quest_id: string | null
  next_quest_id: string | null
  created_at: string
  updated_at: string
}

/**
 * Quest type enum
 */
export type QuestType = 'main' | 'side' | 'daily' | 'event' | 'repeatable'

/**
 * Quest requirement interface
 */
export interface QuestRequirement {
  id: string
  quest_id: string
  requirement_type: 'level' | 'item' | 'room' | 'dweller_count' | 'quest_completed'
  requirement_data: Record<string, unknown>
  is_mandatory: boolean
}

/**
 * Quest reward interface
 */
export interface QuestReward {
  id: string
  quest_id: string
  reward_type:
    | 'caps'
    | 'item'
    | 'dweller'
    | 'resource'
    | 'experience'
    | 'stimpak'
    | 'radaway'
    | 'lunchbox'
  reward_data: Record<string, unknown>
  reward_chance: number
  item_data?: Record<string, unknown>
}

/**
 * Quest party member interface
 */
export interface QuestPartyMember {
  id: string
  quest_id: string
  vault_id: string
  dweller_id: string
  slot_number: number
  status: 'assigned' | 'in_progress' | 'completed' | 'failed'
  created_at: string
  updated_at: string
}

/**
 * Quest with completion status for a specific vault
 */
export interface VaultQuest extends Quest {
  is_visible: boolean
  is_locked: boolean
  lock_reason: string | null
  is_completed: boolean
  is_reward_ready?: boolean
  started_at: string | null
  duration_minutes: number | null
  quest_requirements?: QuestRequirement[]
  quest_rewards?: QuestReward[]
}

/**
 * Payload for creating a new quest (admin only)
 */
export interface QuestCreate {
  title: string
  short_description: string
  long_description: string
  requirements: string
  rewards: string
}

/**
 * Payload for updating a quest (admin only)
 */
export interface QuestUpdate {
  title?: string
  short_description?: string
  long_description?: string
  requirements?: string
  rewards?: string
}

const GRANTED_ICONS: Record<GrantedReward['reward_type'], string> = {
  caps: 'mdi:currency-usd',
  item: 'mdi:package-variant',
  dweller: 'mdi:account-plus',
  resource: 'mdi:database',
  experience: 'mdi:star',
  stimpak: 'mdi:medical-bag',
  radaway: 'mdi:radiation',
}

const GRANTED_LABELS: Record<GrantedReward['reward_type'], string> = {
  caps: 'Bottle Caps',
  item: 'Item',
  dweller: 'New Dweller',
  resource: 'Resource',
  experience: 'Experience',
  stimpak: 'Stimpak',
  radaway: 'RadAway',
}

const GRANTED_ITEM_ICONS: Record<string, string> = {
  weapon: 'mdi:sword-cross',
  outfit: 'mdi:tshirt-crew',
  junk: 'mdi:cog',
  pet: 'mdi:paw',
  consumable: 'mdi:bottle-tonic',
  lunchbox: 'mdi:gift',
}

const GRANTED_ITEM_LABELS: Record<string, string> = {
  weapon: 'Weapon',
  outfit: 'Outfit',
  junk: 'Junk',
  pet: 'Pet',
  consumable: 'Consumable',
  lunchbox: 'Lunchbox',
}

const GRANTED_RESOURCE_ICONS: Record<string, string> = {
  power: 'mdi:flash',
  food: 'mdi:food-apple',
  water: 'mdi:water',
}

const GRANTED_RESOURCE_LABELS: Record<string, string> = {
  power: 'Power',
  food: 'Food',
  water: 'Water',
}

export interface GrantedRewardDisplay {
  icon: string
  label: string
  value: string
}

/**
 * Single presentation mapping for settled rewards, shared by toasts,
 * the quest completion modal, and anywhere else granted rewards render —
 * so every surface agrees exactly with what settlement delivered.
 */
export function describeGrantedReward(reward: GrantedReward): GrantedRewardDisplay {
  switch (reward.reward_type) {
    case 'caps':
      return { icon: GRANTED_ICONS.caps, label: GRANTED_LABELS.caps, value: String(reward.amount) }
    case 'resource':
      return {
        icon: GRANTED_RESOURCE_ICONS[reward.resource_type] ?? GRANTED_ICONS.resource,
        label: GRANTED_RESOURCE_LABELS[reward.resource_type] ?? GRANTED_LABELS.resource,
        value: String(reward.amount),
      }
    case 'experience':
      return {
        icon: GRANTED_ICONS.experience,
        label: GRANTED_LABELS.experience,
        value: reward.name ?? `${reward.amount} XP`,
      }
    case 'dweller':
      return { icon: GRANTED_ICONS.dweller, label: GRANTED_LABELS.dweller, value: reward.name }
    case 'stimpak':
    case 'radaway':
      return {
        icon: GRANTED_ICONS[reward.reward_type],
        label: GRANTED_LABELS[reward.reward_type],
        value: String(reward.amount),
      }
    case 'item': {
      const quantity = reward.amount > 1 ? `${reward.amount}x ` : ''
      return {
        icon: GRANTED_ITEM_ICONS[reward.item_type] ?? GRANTED_ICONS.item,
        label: GRANTED_ITEM_LABELS[reward.item_type] ?? GRANTED_LABELS.item,
        value: `${quantity}${reward.name}`,
      }
    }
  }
}

/** One-line rendering of a settled reward for toasts and log-style surfaces. */
export function formatGrantedReward(reward: GrantedReward): string {
  switch (reward.reward_type) {
    case 'caps':
      return `${reward.amount} caps`
    case 'resource':
      return `${reward.amount} ${reward.resource_type}`
    case 'experience':
      return reward.name ?? `${reward.amount} XP`
    case 'stimpak':
    case 'radaway': {
      const label = reward.reward_type === 'stimpak' ? 'Stimpak' : 'RadAway'
      return `${reward.amount} ${label}`
    }
    default:
      return describeGrantedReward(reward).value
  }
}
