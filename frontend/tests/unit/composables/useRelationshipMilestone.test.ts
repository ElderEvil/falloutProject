import { describe, it, expect } from 'vite-plus/test'
import { useRelationshipMilestone } from '@/modules/social/composables/useRelationshipMilestone'

const rel = (relationship_type: string, affinity: number) =>
  ({ relationship_type, affinity }) as never

const nextMilestone = (relationship_type: string, affinity: number) =>
  useRelationshipMilestone(() => rel(relationship_type, affinity)).nextMilestone.value

describe('useRelationshipMilestone', () => {
  it.each([
    ['acquaintance', 50, '20 hearts until romance'],
    ['acquaintance', 70, 'Romance is within reach'],
    ['romantic', 75, 'Ready to become partners'],
    ['partner', 80, '5 hearts until marriage'],
    ['partner', 85, 'Ready to marry'],
    ['MARRIED', 90, null],
    ['ex', 0, null],
  ] as const)('names the next milestone for a %s at %i affinity', (type, affinity, expected) => {
    expect(nextMilestone(type, affinity)).toBe(expected)
  })
})
