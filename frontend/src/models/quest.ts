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
  created_at: string
  updated_at: string
}

/**
 * Quest with completion status for a specific vault
 */
export interface VaultQuest extends Quest {
  is_visible: boolean
  is_completed: boolean
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
