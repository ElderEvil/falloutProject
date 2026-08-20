import { computed } from 'vue'
import type { Relationship } from '../models/relationship'

export const ROMANCE_THRESHOLD = 70
export const MARRIAGE_THRESHOLD = 85

/**
 * Derive the next actionable relationship milestone (or distance to it) from a
 * relationship's stage and affinity, matching the button-gating thresholds.
 * Returns null when no milestone is pending.
 */
export function useRelationshipMilestone(relationship: () => Relationship) {
  const nextMilestone = computed(() => {
    const { relationship_type, affinity } = relationship()
    if (relationship_type === 'acquaintance' && affinity < ROMANCE_THRESHOLD) {
      return `${ROMANCE_THRESHOLD - affinity} to romance`
    }
    if (relationship_type === 'romantic') {
      return 'romantic — make partners'
    }
    if (relationship_type === 'partner' && affinity < MARRIAGE_THRESHOLD) {
      return `${MARRIAGE_THRESHOLD - affinity} to marry`
    }
    if (relationship_type === 'partner') {
      return 'ready to marry'
    }
    return null
  })

  return { nextMilestone }
}
