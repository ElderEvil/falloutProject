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

export const arenaTeamSize = (mode: ArenaMode): number => (mode === 'brawl' ? 2 : 1)

export const arenaSlotsFor = (mode: ArenaMode, side: ArenaTeamSide): readonly ArenaSlotKey[] =>
  mode === 'brawl' ? ARENA_TEAM_SLOTS[side] : ARENA_TEAM_SLOTS[side].slice(0, 1)
