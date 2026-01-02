/**
 * Objective/Challenge model
 *
 * Represents a challenge or objective for a vault that can be completed
 * for rewards (e.g., "Collect 100 caps", "Train 5 dwellers")
 */
export interface Objective {
  id: string
  vault_id: string
  challenge: string
  progress: number
  total: number
  reward: string
  is_completed: boolean
  created_at: string
  completed_at?: string
}

/**
 * Payload for creating a new objective
 */
export interface ObjectiveCreate {
  challenge: string
  total: number
  reward: string
}

/**
 * Payload for updating objective progress
 */
export interface ObjectiveProgressUpdate {
  progress: number
}
