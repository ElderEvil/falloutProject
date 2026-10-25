import type { CombatSkillIcon } from '@/modules/combat/models/playback'

export interface BattleLogEntry {
  id: string
  kind: string
  message: string
  timestamp?: string | null
  meta?: string | null
  delta?: string | null
  skillIcon?: CombatSkillIcon | null
}

export const battleLogKindLabel = (kind: string, labels: Record<string, string>): string =>
  labels[kind] ?? kind.replace(/_/g, ' ').toUpperCase()
