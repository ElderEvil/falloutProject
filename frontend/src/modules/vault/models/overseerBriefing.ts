export interface OverseerResourceWarning {
  type: string
  message: string
}

export type ReadyActionKind =
  | 'incident_aftermath'
  | 'exploration_outcome'
  | 'quest_claim'
  | 'objective_claim'
  | 'crafting_collect'
  | 'training_complete'

export interface ReadyAction {
  kind: ReadyActionKind
  label: string
  route: string
  count: number
}

export interface OverseerBriefingData {
  vaultNumber: number
  activeIncidentCount: number
  activeExplorationCount: number
  trainingCount: number
  questingCount: number
  unassignedCount: number
  populationUtilization: number
  happiness: number
  resourceWarnings: OverseerResourceWarning[]
  dwellersPath: string
  readyActions: ReadyAction[]
}

export const getOverseerAttentionCount = (briefing: OverseerBriefingData): number =>
  Math.min(
    3,
    Number(briefing.activeIncidentCount > 0) +
      Math.min(briefing.resourceWarnings.length, 2) +
      Number(briefing.unassignedCount > 0) +
      Number(briefing.populationUtilization >= 90) +
      Number(briefing.happiness < 50)
  )
