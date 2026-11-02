import type { components } from '@/core/types/api.generated'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import { getDwellerDisplayName, isMature } from '@/modules/dwellers/models/dweller'
import type { SoundKey } from '@/core/audio/soundManifest'

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

export interface IncidentLootItem {
  item_type: string
  rarity?: string
  name: string
  quantity?: number
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
    experience?: number
    items?: IncidentLootItem[]
  } | null
  unclaimed_loot: IncidentLootItem[]
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
  events: components['schemas']['IncidentEventRead'][]
}

export type PendingIncidentOverflow = components['schemas']['PendingIncidentOverflowRead']

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

export const INCIDENT_SOUND_MAP: Record<IncidentType, SoundKey> = {
  [IncidentType.RAIDER_ATTACK]: 'incidentRaider',
  [IncidentType.RADROACH_INFESTATION]: 'incidentRadroach',
  [IncidentType.MOLE_RAT_ATTACK]: 'incidentMolerat',
  [IncidentType.FERAL_GHOUL_ATTACK]: 'incidentFeralGhoul',
  [IncidentType.RADSCORPION_ATTACK]: 'incidentRadscorpion',
  [IncidentType.DEATHCLAW_ATTACK]: 'incidentDeathclaw',
  [IncidentType.FIRE]: 'incidentFire',
}

export function getIncidentSound(type: IncidentType): SoundKey {
  return INCIDENT_SOUND_MAP[type] ?? 'incidentRadroach'
}

export type IncidentOutcome = 'victory' | 'defeat' | 'unknown'

export interface IncidentAftermath {
  incidentId: string
  roomId: string
  type: IncidentType
  roomName: string | null
  outcome: IncidentOutcome
  capsEarned: number
  experienceEarned: number
  loot: Incident['loot']
  unclaimed: IncidentLootItem[]
  enemiesDefeated: number
  damageDealt: number
  rounds: number
  scene?: Incident
  sceneLoading?: boolean
}

export interface IncidentOverflowResponse {
  caps_granted: number
  unclaimed_loot: IncidentLootItem[]
}

export interface IncidentTeamMember {
  id: string
  team_id: string
  dweller_id: string
  slot_number: number | null
  origin_room_id?: string | null
  status: string
  created_at: string | null
  updated_at: string | null
}

export interface IncidentParticipant {
  id: string
  dweller: DwellerShort | undefined
  name: string
  source: 'resident' | 'helper'
  originRoomId?: string | null
  dispatched: boolean
}

/** Room residents defend automatically; sent responders add to that group. */
export function getIncidentParticipants(
  roomId: string,
  dwellers: DwellerShort[],
  team: IncidentTeamMember[] = []
): IncidentParticipant[] {
  const helpers = team.filter((member) => {
    if (!['assigned', 'dispatched'].includes(member.status)) return false
    const dweller = dwellers.find((dweller) => dweller.id === member.dweller_id)
    return (
      !dweller ||
      (dweller.room_id === roomId && !['exploring', 'questing'].includes(dweller.status))
    )
  })
  const helperIds = new Set(helpers.map((member) => member.dweller_id))
  const residents: IncidentParticipant[] = dwellers
    .filter(
      (dweller) =>
        dweller.room_id === roomId &&
        isMature(dweller) &&
        dweller.health > 0 &&
        dweller.status !== 'dead' &&
        !helperIds.has(dweller.id)
    )
    .map((dweller) => ({
      id: dweller.id,
      dweller,
      name: getDwellerDisplayName(dweller),
      source: 'resident',
      dispatched: false,
    }))
  return [
    ...residents,
    ...[...helpers]
      .sort((a, b) => (a.slot_number ?? 0) - (b.slot_number ?? 0))
      .map((member, index): IncidentParticipant => {
        const dweller = dwellers.find((dweller) => dweller.id === member.dweller_id)
        return {
          id: member.dweller_id,
          dweller,
          name: dweller
            ? getDwellerDisplayName(dweller)
            : `Responder ${member.slot_number ?? index + 1}`,
          source: 'helper',
          originRoomId: member.origin_room_id,
          dispatched: member.status === 'dispatched',
        }
      }),
  ]
}

export type IncidentRespondersResponse = components['schemas']['IncidentRespondersResponse']
