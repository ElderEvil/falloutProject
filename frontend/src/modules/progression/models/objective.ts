/**
 * Objective/Challenge model
 *
 * Represents a challenge or objective for a vault that can be completed
 * for rewards (e.g., "Collect 100 caps", "Train 5 dwellers")
 */
export type ObjectiveCategory = 'daily' | 'weekly' | 'achievement' | 'starter'

export type ObjectiveType =
  | 'assign'
  | 'assign_correct'
  | 'build'
  | 'collect'
  | 'expedition'
  | 'level_up'
  | 'reach'
  | 'scrap'
  | 'train'

export interface Objective {
  id: string
  vault_id: string
  challenge: string
  progress: number
  total: number
  reward: string
  is_completed: boolean
  category: ObjectiveCategory
  objective_type?: ObjectiveType
  target_entity?: Record<string, unknown>
  sequence?: number | null
  description?: string | null
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

/** The guided arc stays on the current step until its reward is claimed. */
export function currentObjective(objectives: Objective[]): Objective | undefined {
  const active = objectives.filter((objective) => !objective.is_completed)
  return (
    active
      .filter((objective) => objective.category === 'starter')
      .sort((a, b) => (a.sequence ?? Infinity) - (b.sequence ?? Infinity))[0] ??
    active.find((objective) => objective.progress >= objective.total) ??
    active[0]
  )
}

/** Existing game surfaces relevant to each objective, without inventing new routes. */
export function objectiveActionPath(objective: Objective, vaultId: string): string {
  const vault = `/vault/${vaultId}`
  switch (objective.objective_type) {
    case 'train':
      return `${vault}/training`
    case 'expedition':
      return `${vault}/quests`
    case 'scrap':
      return `${vault}/storage`
    case 'collect':
      return objective.target_entity?.resource_type === 'caps' ? `${vault}/exploration` : vault
    case 'reach':
      return objective.target_entity?.reach_type === 'dweller_count'
        ? `${vault}/relationships`
        : `${vault}/dwellers`
    case 'assign':
    case 'assign_correct':
    case 'level_up':
      return `${vault}/dwellers`
    default:
      return vault
  }
}
