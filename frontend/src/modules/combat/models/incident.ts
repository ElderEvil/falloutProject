export enum IncidentType {
  RAIDER_ATTACK = 'raider_attack',
  RADROACH_INFESTATION = 'radroach_infestation',
  MOLE_RAT_ATTACK = 'mole_rat_attack',
  DEATHCLAW_ATTACK = 'deathclaw_attack',
  FERAL_GHOUL_ATTACK = 'feral_ghoul_attack',
  FIRE = 'fire',
  RADIATION_LEAK = 'radiation_leak',
  ELECTRICAL_FAILURE = 'electrical_failure',
  WATER_CONTAMINATION = 'water_contamination',
}

export enum IncidentStatus {
  ACTIVE = 'active',
  SPREADING = 'spreading',
  RESOLVED = 'resolved',
  FAILED = 'failed',
}

export interface Incident {
  id: string
  vault_id: string
  room_id: string
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
}

export interface IncidentListResponse {
  vault_id: string
  incident_count: number
  incidents: Array<{
    id: string
    type: IncidentType
    status: IncidentStatus
    room_id: string
    difficulty: number
    start_time: string
    elapsed_time: number
    damage_dealt: number
    enemies_defeated: number
  }>
}

export interface IncidentResolveResponse {
  message: string
  incident_id: string
  loot: {
    caps?: number
    items?: Array<{
      type: string
      rarity?: string
      name: string
      quantity?: number
    }>
  } | null
  caps_earned: number
  items_earned: Array<{
    type: string
    rarity?: string
    name: string
    quantity?: number
  }>
}
