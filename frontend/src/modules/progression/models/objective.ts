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
  | 'equip'
  | 'explore'
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
  template_key?: string | null
  target_entity?: Record<string, unknown>
  track_key?: string | null
  next_stage_challenge?: string | null
  resets_at?: string | null
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

const descriptions = new Map([
  ['collect:water', 'Keep the taps running. Every drop helps the vault.'],
  ['collect:food', 'Keep the diner stocked and your residents fed.'],
  ['collect:power', 'Keep the lights on. Your vault runs on reliable power.'],
  ['collect:caps', 'Caps keep the vault moving. Add a little more to the treasury.'],
  ['collect', 'Stock up on supplies. Life underground rewards a prepared Overseer.'],
  ['assign', 'Every resident has a part to play. Give your dwellers a job.'],
  ['assign_correct', 'The right resident in the right room. Put your dwellers’ talents to work.'],
  ['build', 'Make room for a better life underground.'],
  ['train', 'Turn spare time into SPECIAL skills.'],
  ['equip', 'The wasteland doesn’t fight fair. Give your dwellers an edge.'],
  ['explore', 'There’s a whole wasteland beyond that door. Send a dweller out to explore.'],
  ['expedition', 'Send a team beyond the vault door and bring them home.'],
  ['level_up', 'Experience keeps a dweller alive. Help yours grow stronger.'],
  ['reach', 'Build a vault worth calling home.'],
  ['scrap', 'Nothing goes to waste down here. Salvage what you can.'],
])

export function objectiveDescription(objective: Objective): string | null {
  if (objective.description) return objective.description
  if (objective.objective_type === 'assign_correct' && objective.target_entity?.distinct_dwellers)
    return 'The right resident in the right room. Put different dwellers’ talents to work.'
  const resource = objective.target_entity?.resource_type
  return (
    descriptions.get(
      `${objective.objective_type ?? ''}:${typeof resource === 'string' ? resource : ''}`
    ) ??
    descriptions.get(objective.objective_type ?? '') ??
    null
  )
}

/** A starter row kept for its progress links that no longer advances the arc. */
export function isRetiredStarter(objective: Objective): boolean {
  return objective.category === 'starter' && !objective.objective_type
}

/** The guided arc stays on the current step until its reward is claimed. */
export function currentObjective(objectives: Objective[]): Objective | undefined {
  const active = objectives.filter(
    (objective) => !objective.is_completed && !isRetiredStarter(objective)
  )
  return (
    active
      .filter((objective) => objective.category === 'starter')
      .sort((a, b) => (a.sequence ?? Infinity) - (b.sequence ?? Infinity))[0] ??
    active.find((objective) => objective.progress >= objective.total) ??
    active[0]
  )
}

/** A finished objective whose reward the owner has not claimed yet. */
export function isObjectiveClaimable(objective: Objective): boolean {
  return !objective.is_completed && objective.progress >= objective.total
}

export function isOfficeObjective(objective: Objective): boolean {
  return (
    objective.objective_type === 'build' &&
    objective.target_entity?.room_type === 'overseers_office'
  )
}

/** Named rewards use the same single-item format as backend settlement. */
export function objectiveRewardDetails(reward: string) {
  const [rawPrefix, value, itemName] = reward.split(':')
  const prefix = rawPrefix.toLowerCase()
  if ((prefix === 'weapon' || prefix === 'outfit') && value) {
    return {
      kind: 'item' as const,
      name: itemName ?? value,
      itemType: prefix,
      rarity: itemName ? value : 'common',
    }
  }
  if (prefix === 'dweller' && value) return { kind: 'dweller' as const, name: value }
  return { kind: 'currency' as const, name: reward }
}

/** Existing game surfaces relevant to each objective, without inventing new routes. */
export function objectiveActionPath(objective: Objective, vaultId: string): string {
  const vault = `/vault/${vaultId}`
  switch (objective.objective_type) {
    case 'train':
      return `${vault}/training`
    case 'expedition':
      return `${vault}/quests`
    case 'explore':
      return `${vault}/exploration`
    case 'scrap':
    case 'equip':
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
