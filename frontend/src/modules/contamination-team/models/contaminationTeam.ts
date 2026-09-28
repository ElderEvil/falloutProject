import type { components } from '@/core/types/api.generated'

export type ContaminationTeamRead = components['schemas']['ContaminationTeamRead']
export type HazardTeamRosterRead = components['schemas']['HazardTeamRosterRead']
export type HazardTeamMemberRead = components['schemas']['HazardTeamMemberRead']
export type HazardTeam = components['schemas']['HazardTeam'] // 'fire' | 'radiation'

/** Max active members per team, mirroring the backend TEAM_SIZE. */
export const HAZARD_TEAM_SIZE = 3
