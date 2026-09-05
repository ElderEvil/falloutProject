export enum IncidentType {
  RAIDER_ATTACK = 'raider_attack',
  RADROACH_INFESTATION = 'radroach_infestation',
  MOLE_RAT_ATTACK = 'mole_rat_attack',
  DEATHCLAW_ATTACK = 'deathclaw_attack',
  FERAL_GHOUL_ATTACK = 'feral_ghoul_attack',
  RADSCORPION_ATTACK = 'radscorpion_attack',
  FIRE = 'fire',
}

export enum IncidentStatus {
  ACTIVE = 'active',
  SPREADING = 'spreading',
  RESOLVED = 'resolved',
  FAILED = 'failed',
}

export type IncidentFamily = 'hazard' | 'infestation' | 'intrusion'
export type IncidentObjective = 'contain' | 'defeat'

export interface IncidentProgress {
  current: number
  target: number
  label: string
}

export interface Incident {
  id: string
  vault_id: string
  room_id: string
  room_name: string | null
  type: IncidentType
  status: IncidentStatus
  difficulty: number
  start_time: string
  end_time: string | null
  duration: number
  elapsed_time: number
  damage_dealt: number
  enemies_defeated: number
  loot: {
    caps?: number
    items?: Array<{
      type: string
      rarity?: string
      name: string
      quantity?: number
    }>
  } | null
  rooms_affected: string[]
  spread_count: number
  created_at: string
  updated_at: string
  family: IncidentFamily
  objective: IncidentObjective
  progress: IncidentProgress
  risk: {
    kind: string
    rooms_affected: number
  }
  response: {
    label: string
  }
  events: Array<{
    id: string
    kind: string
    message: string
    data: Record<string, number | string> | null
  }>
}

export interface IncidentListResponse {
  vault_id: string
  incident_count: number
  incidents: Array<{
    id: string
    type: IncidentType
    status: IncidentStatus
    room_id: string
    room_name: string | null
    difficulty: number
    start_time: string
    elapsed_time: number
    damage_dealt: number
    enemies_defeated: number
  }>
}

export const INCIDENT_ICON_MAP: Record<IncidentType, string> = {
  [IncidentType.RAIDER_ATTACK]: 'mdi:robber',
  [IncidentType.RADROACH_INFESTATION]: 'mdi:bug',
  [IncidentType.FIRE]: 'mdi:fire',
  [IncidentType.MOLE_RAT_ATTACK]: 'mdi:paw',
  [IncidentType.DEATHCLAW_ATTACK]: 'mdi:axe-battle',
  [IncidentType.FERAL_GHOUL_ATTACK]: 'mdi:biohazard',
  [IncidentType.RADSCORPION_ATTACK]: 'mdi:spider',
}

export function getIncidentIcon(type: IncidentType): string {
  return INCIDENT_ICON_MAP[type] ?? 'mdi:alert-octagon'
}
