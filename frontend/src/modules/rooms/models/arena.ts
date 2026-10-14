import type { ArenaFighter, ArenaMode } from '../api/arena'

export type ArenaSlotKey = 'a' | 'b' | 'c' | 'd'
export type ArenaTeamSide = 'A' | 'B'

// Slot order per side: the lead first, the brawl second slot after it.
export const ARENA_TEAM_SLOTS: Record<ArenaTeamSide, readonly ArenaSlotKey[]> = {
  A: ['a', 'c'],
  B: ['b', 'd'],
}

// `power: null` marks a pick the server has not confirmed yet: bench entries
// carry no combat power, so a pending slot shows the rest of the card only.
export interface ArenaSlotFighter extends Omit<ArenaFighter, 'power'> {
  power: number | null
}

// A creature on team B in hunt mode: catalog stats, overlaid with the server's
// live values (and participant id) once the selection is committed.
export interface ArenaCreatureView {
  key: string
  name: string
  power: number
  health: number
  max_health: number
  id: string | null
}

// Creature participant ids are `<catalog-key>#<index>` (see ArenaService).
export const creatureKeyOf = (fighterId: string): string => fighterId.split('#')[0]

export const arenaTeamSize = (mode: ArenaMode): number => (mode === 'brawl' ? 2 : 1)

export const arenaSlotsFor = (mode: ArenaMode, side: ArenaTeamSide): readonly ArenaSlotKey[] => {
  if (mode === 'hunt') return side === 'A' ? ARENA_TEAM_SLOTS.A : []
  return mode === 'brawl' ? ARENA_TEAM_SLOTS[side] : ARENA_TEAM_SLOTS[side].slice(0, 1)
}
