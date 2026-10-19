import type { components } from '@/core/types/api.generated'

export type CombatZoneLobbyRead = components['schemas']['CombatZoneLobbyRead']
export type CombatZoneLobbyParty = components['schemas']['CombatZoneLobbyParty']
export type CombatZoneMatchRead = components['schemas']['CombatZoneMatchRead']
export type CombatZoneMatchPartyRead = components['schemas']['CombatZoneMatchPartyRead']
export type CombatZoneMatchSummary = components['schemas']['CombatZoneMatchSummary']
export type CombatZonePartyRead = components['schemas']['CombatZonePartyRead']
export type CombatZonePartyStatus = components['schemas']['CombatZonePartyStatus']
export type CombatZoneStance = components['schemas']['CombatZoneStance']
export type CombatZoneEventRead = components['schemas']['CombatZoneEventRead']

export const STANCE_OPTIONS: ReadonlyArray<{
  value: CombatZoneStance
  label: string
  icon: string
  hint: string
}> = [
  {
    value: 'aggressive',
    label: 'Aggressive',
    icon: 'mdi:sword',
    hint: 'Pressure. Strong into Focus.',
  },
  {
    value: 'defensive',
    label: 'Defensive',
    icon: 'mdi:shield',
    hint: 'Guard. Strong into Aggressive.',
  },
  {
    value: 'focus',
    label: 'Focus',
    icon: 'mdi:crosshairs',
    hint: 'Precision. Strong into Defensive.',
  },
  {
    value: 'retreat',
    label: 'Retreat',
    icon: 'mdi:run',
    hint: 'Forfeit after 6 s. The purse goes to the opponent.',
  },
]

const PARTY_STATUS_LABELS: Record<CombatZonePartyStatus, string> = {
  traveling: 'Travelling to the interchange',
  queued: 'Waiting at the bell',
  in_match: 'Bout in progress',
  returning: 'Returning to the vault',
  home: 'At the vault',
}

export function partyStatusLabel(status: CombatZonePartyStatus): string {
  return PARTY_STATUS_LABELS[status] ?? status
}

export function isPartyDeployed(party: CombatZonePartyRead | null): boolean {
  return party !== null && party.status !== 'home'
}

export function stanceLabel(stance: CombatZoneStance): string {
  return STANCE_OPTIONS.find((option) => option.value === stance)?.label ?? stance
}

/** Seconds until an ISO timestamp, floored at zero. */
export function secondsUntil(iso: string | null | undefined, nowMs: number): number {
  if (!iso) return 0
  const target = new Date(iso).getTime()
  if (Number.isNaN(target)) return 0
  return Math.max(0, Math.ceil((target - nowMs) / 1000))
}
