/**
 * Quest model
 *
 * Represents a quest/mission that can be assigned to a vault and completed for rewards.
 * Quests are only accessible when the Overseer's Office is built.
 */
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
  is_completed: boolean
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
