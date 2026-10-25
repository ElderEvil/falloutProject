import type { components } from '@/core/types/api.generated'

export type CombatAction = components['schemas']['CombatAction']
export type CombatImpact = components['schemas']['CombatImpact']
export type CombatEffect = NonNullable<CombatAction['effect']>
export type CombatSkillIcon = NonNullable<CombatAction['skill_icon']>

export interface CombatPlaybackEvent {
  id: string
  message: string
  action?: CombatAction | null
}

export interface CombatPlaybackSnapshot {
  key: string
  health: Record<string, number>
  events: CombatPlaybackEvent[]
}

export interface PlayingCombatAction extends CombatPlaybackEvent {
  action: CombatAction
  accelerated?: boolean
}
