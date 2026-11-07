import type { DwellerShort } from '@/modules/dwellers/models/dweller'

/**
 * Send-team ordering for the location details picker: dwellers without a job
 * (no room assignment) first, then employed dwellers grouped by room name.
 * Array#sort is stable, so the caller's default order survives within each
 * group — including idle dwellers and co-workers in the same room.
 */
export function sortDepartureCandidates(
  dwellers: readonly DwellerShort[],
  roomNameById: ReadonlyMap<string, string>
): DwellerShort[] {
  return [...dwellers].sort((a, b) => {
    const aJob = a.room_id ? (roomNameById.get(a.room_id) ?? '') : null
    const bJob = b.room_id ? (roomNameById.get(b.room_id) ?? '') : null
    if (aJob === null || bJob === null) {
      return Number(aJob !== null) - Number(bJob !== null)
    }
    return aJob.localeCompare(bJob)
  })
}
