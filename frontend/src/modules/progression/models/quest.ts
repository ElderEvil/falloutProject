/**
 * Quest model
 *
 * Represents a quest/mission that can be assigned to a vault and completed for rewards.
 * Quests are only accessible when the Overseer's Office is built.
 */
import type { components } from '@/core/types/api.generated'
import { getItemIcon } from '@/core/models/items'
import { capitalize } from '@/core/utils/format'

export type GrantedReward =
  components['schemas']['QuestCompleteResponse']['granted_rewards'][number]
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
  requirement_type:
    | 'level'
    | 'item'
    | 'room'
    | 'dweller_count'
    | 'quest_completed'
    | 'attack'
    | 'stat'
  requirement_data: Record<string, unknown>
  is_mandatory: boolean
  /** Backend vault-scoped verdict from the read path; null when not evaluated. */
  is_met?: boolean | null
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
  return_started_at: string | null
  return_completes_at: string | null
  completed_at: string | null
  granted_rewards?: GrantedReward[] | null
  quest_requirements?: QuestRequirement[]
  quest_rewards?: QuestReward[]
}

/** True while a quest party is travelling home and rewards are not yet claimable. */
export function isQuestReturning(quest: VaultQuest): boolean {
  return quest.return_completes_at != null && !quest.is_reward_ready && !quest.is_completed
}

/** Timed-quest slots for a vault, read from its Overseer's Office tier. */
export function questSlotLimitForVault(
  rooms: { category: string; tier: number }[],
  loadedVaultId: string | null,
  vaultId: string
): number {
  if (loadedVaultId !== vaultId) return 0
  return rooms.find((room) => room.category === 'quests')?.tier ?? 0
}

/** Display name for an authored dweller reward, without the rarity suffix. */
export function questDwellerName(reward: QuestReward): string {
  const data = reward.reward_data || {}
  const template = rewardText(data.template_id).replaceAll('-', ' ')
  const raw = rewardText(data.first_name) || rewardText(data.name) || template || 'New Dweller'
  return raw.replace(/(^|[\s-])\p{L}/gu, (letter) => letter.toUpperCase())
}

/** Human-readable label for a quest reward (amount + name), shared by card and detail views. */
export function formatQuestReward(reward: QuestReward): string {
  const data = reward.reward_data || {}
  const itemData = reward.item_data || {}
  const type = reward.reward_type.toLowerCase()

  switch (type) {
    case 'caps':
      return `${rewardAmount(data.amount)} Caps`
    case 'resource': {
      const resourceType = rewardText(data.resource_type) || 'resource'
      return `${rewardAmount(data.amount)} ${capitalize(resourceType)}`
    }
    case 'experience':
      return `${rewardAmount(data.amount)} XP`
    case 'item': {
      const itemName =
        rewardText(data.item_name) ||
        rewardText(itemData.name) ||
        rewardText(data.name) ||
        'Unknown Item'
      const category = rewardText(
        reward.item_data?.item_type ?? reward.reward_data?.item_type
      ).toLowerCase()
      const lowerName = itemName.toLowerCase()
      const isConsumable =
        category === 'consumable' || lowerName.includes('stimpak') || lowerName.includes('radaway')
      const rarityValue = rewardText(itemData.rarity) || rewardText(data.rarity)
      const rarity = !isConsumable && rarityValue ? ` (${rarityValue})` : ''
      return `${itemName}${rarity}`
    }
    case 'dweller': {
      const rarityValue = rewardText(data.rarity)
      const rarity = rarityValue ? ` (${rarityValue})` : ''
      return `${questDwellerName(reward)}${rarity}`
    }
    case 'stimpak': {
      const amt = Number(data.amount) || 1
      return `${amt} Stimpak${amt > 1 ? 's' : ''}`
    }
    case 'radaway': {
      const amt = Number(data.amount) || 1
      return `${amt} Radaway${amt > 1 ? 's' : ''}`
    }
    case 'lunchbox':
      return 'Lunchbox (3 items + 1 dweller)'
    default:
      return capitalize(type)
  }
}

/** Item-category icon for quest rewards, derived from the shared item icon source. */
export function questCategoryIcon(category: string): string {
  return getItemIcon(category, {})
}

function rewardText(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

function rewardAmount(value: unknown): number {
  return typeof value === 'number' ? value : Number(value) || 0
}

/** Type chip colors shared by the quest card and detail badges. */
export const QUEST_TYPE_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  main: { bg: 'var(--color-theme-primary)', text: '#000000', border: 'var(--color-theme-primary)' },
  side: {
    bg: 'var(--color-quest-side)',
    text: 'var(--color-theme-primary)',
    border: 'var(--color-quest-side)',
  },
  daily: { bg: 'var(--color-quest-daily)', text: '#000000', border: 'var(--color-quest-daily)' },
  event: { bg: 'var(--color-quest-event)', text: '#ffffff', border: 'var(--color-quest-event)' },
  repeatable: {
    bg: 'var(--color-theme-primary)',
    text: '#000000',
    border: 'var(--color-theme-primary)',
  },
}

export function questTypeLabel(questType: string | null | undefined): string {
  const normalized = questType || 'side'
  return capitalize(normalized)
}

export function isSideQuestType(questType: string | null | undefined): boolean {
  return (questType || 'side') === 'side'
}

/** State quests settle from vault progress and start without a party. */
export function isStateQuestCategory(category: string | null | undefined): boolean {
  return ['building', 'population', 'training'].includes(category ?? '')
}

export type QuestAvailableSortBy = 'level' | 'duration' | 'type'

/** Highest dweller level the quest's level requirements demand; 0 when unconstrained. */
export function questRequiredLevel(quest: VaultQuest): number {
  return (quest.quest_requirements ?? []).reduce((highest, requirement) => {
    if (requirement.requirement_type !== 'level') return highest
    const level = requirement.requirement_data.level
    return typeof level === 'number' ? Math.max(highest, level) : highest
  }, 0)
}

/** Order available quests so the most reachable ones surface first; title breaks ties. */
export function compareQuestsByAvailableSort(
  a: VaultQuest,
  b: VaultQuest,
  sortBy: QuestAvailableSortBy
): number {
  const primary =
    sortBy === 'duration'
      ? (a.duration_minutes ?? 0) - (b.duration_minutes ?? 0)
      : sortBy === 'type'
        ? (a.quest_type ?? '').localeCompare(b.quest_type ?? '')
        : questRequiredLevel(a) - questRequiredLevel(b)
  return primary || a.title.localeCompare(b.title)
}

/** Humanize a backend slug for display: underscores become spaces, first letter capitalized. */
export function humanizeSlug(value: unknown): string {
  const label = rewardText(value) || 'stat'
  return capitalize(label.replace(/_/g, ' '))
}

/** Icon for a quest reward; item rewards resolve via category, then item name, so only unknown items use the generic icon. */
export function questRewardIcon(reward: QuestReward): string {
  const type = reward.reward_type.toLowerCase()
  if (type === 'item') {
    const category = rewardText(
      reward.item_data?.item_type ?? reward.reward_data?.item_type
    ).toLowerCase()
    if (category && category in QUEST_ITEM_LABELS) return questCategoryIcon(category)
    const itemName = rewardText(
      reward.reward_data?.item_name || reward.item_data?.name || reward.reward_data?.name
    ).toLowerCase()
    if (itemName.includes('stimpak')) return REWARD_TYPE_META.stimpak.icon
    if (itemName.includes('radaway')) return REWARD_TYPE_META.radaway.icon
    return REWARD_TYPE_META.item.icon
  }
  if (type === 'resource') {
    const resourceType = rewardText(reward.reward_data?.resource_type)
    return RESOURCE_META[resourceType]?.icon ?? REWARD_TYPE_META.resource.icon
  }
  return REWARD_TYPE_META[type as QuestReward['reward_type']]?.icon ?? 'mdi:gift'
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

/** Shared reward-type icon-and-label metadata for advertised and granted rewards. */
export const REWARD_TYPE_META: Record<QuestReward['reward_type'], { icon: string; label: string }> =
  {
    caps: { icon: 'mdi:coins', label: 'Bottle Caps' },
    item: { icon: 'mdi:package-variant', label: 'Item' },
    dweller: { icon: 'mdi:account-plus', label: 'New Dweller' },
    resource: { icon: 'mdi:database', label: 'Resource' },
    experience: { icon: 'mdi:star', label: 'Experience' },
    stimpak: { icon: 'mdi:medical-bag', label: 'Stimpak' },
    radaway: { icon: 'mdi:radiation', label: 'RadAway' },
    lunchbox: { icon: 'mdi:gift', label: 'Lunchbox' },
  }

export const QUEST_ITEM_LABELS: Record<string, string> = {
  weapon: 'Weapon',
  outfit: 'Outfit',
  junk: 'Junk',
  pet: 'Pet',
  consumable: 'Consumable',
  lunchbox: 'Lunchbox',
  dweller: 'Dweller',
}

/** Shared resource icon-and-label metadata for advertised and granted rewards. */
export const RESOURCE_META: Record<string, { icon: string; label: string }> = {
  power: { icon: 'mdi:flash', label: 'Power' },
  food: { icon: 'mdi:silverware', label: 'Food' },
  water: { icon: 'mdi:water', label: 'Water' },
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
      return { ...REWARD_TYPE_META.caps, value: String(reward.amount) }
    case 'resource': {
      const meta = RESOURCE_META[reward.resource_type]
      return {
        icon: meta?.icon ?? REWARD_TYPE_META.resource.icon,
        label: meta?.label ?? REWARD_TYPE_META.resource.label,
        value: String(reward.amount),
      }
    }
    case 'experience':
      return {
        ...REWARD_TYPE_META.experience,
        value: reward.name ?? `${reward.amount} XP`,
      }
    case 'dweller':
      return { ...REWARD_TYPE_META.dweller, value: reward.name }
    case 'stimpak':
    case 'radaway': {
      const meta = REWARD_TYPE_META[reward.reward_type]
      return {
        icon: meta.icon,
        label: meta.label,
        // amount 0 renders as the bare label, matching the backend summary ("RadAway", not "0 RadAway").
        value: reward.amount ? String(reward.amount) : meta.label,
      }
    }
    case 'item': {
      const quantity = reward.amount > 1 ? `${reward.amount}x ` : ''
      return {
        icon: questCategoryIcon(reward.item_type),
        label: QUEST_ITEM_LABELS[reward.item_type] ?? REWARD_TYPE_META.item.label,
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
      // amount 0 renders as the bare label, matching the backend summary ("RadAway", not "0 RadAway").
      return reward.amount ? `${reward.amount} ${label}` : label
    }
    default:
      return describeGrantedReward(reward).value
  }
}
