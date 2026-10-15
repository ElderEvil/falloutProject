import { describe, expect, it } from 'vitest'
import { isObjectiveClaimable, type Objective } from '@/modules/progression/models/objective'

const objective = (overrides: Partial<Objective> = {}): Objective => ({
  id: 'obj-1',
  vault_id: 'vault-1',
  challenge: 'Collect 100 caps',
  progress: 0,
  total: 100,
  reward: '50 Caps',
  is_completed: false,
  category: 'daily',
  created_at: '',
  ...overrides,
})

describe('isObjectiveClaimable', () => {
  it('is true only when the target is reached and the reward is still unclaimed', () => {
    expect(isObjectiveClaimable(objective({ progress: 100, total: 100 }))).toBe(true)
    expect(isObjectiveClaimable(objective({ progress: 150, total: 100 }))).toBe(true)
    expect(isObjectiveClaimable(objective({ progress: 99, total: 100 }))).toBe(false)
    expect(isObjectiveClaimable(objective({ progress: 100, total: 100, is_completed: true }))).toBe(
      false
    )
  })
})
