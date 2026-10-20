export interface BattleLogEntry {
  id: string
  kind: string
  message: string
  timestamp?: string | null
  meta?: string | null
  delta?: string | null
}

export const battleLogKindLabel = (kind: string, labels: Record<string, string>): string =>
  labels[kind] ?? kind.replace(/_/g, ' ').toUpperCase()
