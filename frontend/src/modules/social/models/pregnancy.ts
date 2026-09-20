/**
 * TypeScript models for pregnancy tracking
 */

export type PregnancyStatus = 'pregnant' | 'delivered' | 'miscarried'

/** A pregnancy record for a couple, including progress toward delivery. */
export interface Pregnancy {
  id: string
  mother_id: string
  father_id: string
  conceived_at: string
  due_at: string
  status: PregnancyStatus
  progress_percentage: number // 0-100
  time_remaining_seconds: number
  is_due: boolean
  created_at?: string
  updated_at?: string
}

/** Progress snapshot of a pregnancy, without audit timestamps. */
export interface PregnancyProgress {
  id: string
  mother_id: string
  father_id: string
  status: PregnancyStatus
  conceived_at: string
  due_at: string
  progress_percentage: number
  time_remaining_seconds: number
  is_due: boolean
}

/** Result of delivering a baby, linking the newborn dweller. */
export interface DeliveryResult {
  pregnancy_id: string
  child_id: string
  message: string
}

/**
 * Find the active pregnancy for a couple, matching the (mother, father) pair in
 * either order. Returns null when the couple has no pregnancy in 'pregnant'
 * status.
 */
export function pregnancyForCouple(
  pregnancies: readonly Pregnancy[],
  dweller1Id: string,
  dweller2Id: string
): Pregnancy | null {
  return (
    pregnancies.find(
      (p) =>
        p.status === 'pregnant' &&
        ((p.mother_id === dweller1Id && p.father_id === dweller2Id) ||
          (p.mother_id === dweller2Id && p.father_id === dweller1Id))
    ) ?? null
  )
}
