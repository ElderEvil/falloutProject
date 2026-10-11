import type { components } from '@/core/types/api.generated'

export type ContaminationTeamRead = components['schemas']['ContaminationTeamRead']
export type HazardTeamRosterRead = components['schemas']['HazardTeamRosterRead']
export type HazardTeamMemberRead = components['schemas']['HazardTeamMemberRead']
export type HazardTeam = components['schemas']['HazardTeam'] // 'fire' | 'radiation'

/** Max active members per team, mirroring the backend TEAM_SIZE. */
export const HAZARD_TEAM_SIZE = 3

/** Shared presentation metadata for roster cards and dweller membership chips. */
export const HAZARD_TEAM_CONFIG: Record<
  HazardTeam,
  { label: string; icon: string; description: string }
> = {
  fire: {
    label: 'Fire',
    icon: 'mdi:fire',
    description: 'Contain vault fires and reduce matching hazard damage.',
  },
  radiation: {
    label: 'Radiation',
    icon: 'mdi:radioactive',
    description: 'Answer radscorpion incidents and reduce matching radiation exposure.',
  },
}
