import { describe, it, expect } from 'vitest'
import { useRelationshipMilestone } from '@/modules/social/composables/useRelationshipMilestone'

function rel(relationship_type: string, affinity: number) {
  return { relationship_type, affinity } as never
}

describe('useRelationshipMilestone', () => {
  it('shows distance to romance for a low-affinity acquaintance', () => {
    const { nextMilestone } = useRelationshipMilestone(() => rel('acquaintance', 50))
    expect(nextMilestone.value).toBe('20 hearts until romance')
  })

  it('shows romance as available at the threshold', () => {
    const { nextMilestone } = useRelationshipMilestone(() => rel('acquaintance', 70))
    expect(nextMilestone.value).toBe('Romance is within reach')
  })

  it('prompts to make partners for a romantic relationship', () => {
    const { nextMilestone } = useRelationshipMilestone(() => rel('romantic', 75))
    expect(nextMilestone.value).toBe('Ready to become partners')
  })

  it('shows distance to marriage for a partner below the threshold', () => {
    const { nextMilestone } = useRelationshipMilestone(() => rel('partner', 80))
    expect(nextMilestone.value).toBe('5 hearts until marriage')
  })

  it('reports ready to marry for a partner at the threshold', () => {
    const { nextMilestone } = useRelationshipMilestone(() => rel('partner', 85))
    expect(nextMilestone.value).toBe('Ready to marry')
  })

  it('returns null for married and ex relationships', () => {
    expect(useRelationshipMilestone(() => rel('MARRIED', 90)).nextMilestone.value).toBeNull()
    expect(useRelationshipMilestone(() => rel('ex', 0)).nextMilestone.value).toBeNull()
  })
})
