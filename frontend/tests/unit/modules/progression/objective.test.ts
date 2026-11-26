import { describe, expect, it } from 'vite-plus/test'
import {
  objectiveActionPath,
  isObjectiveClaimable,
  isRetiredStarter,
  type Objective,
} from '@/modules/progression/models/objective'

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
  it.each([
    [{ progress: 100, total: 100 }, true],
    [{ progress: 150, total: 100 }, true],
    [{ progress: 99, total: 100 }, false],
    [{ progress: 100, total: 100, is_completed: true }, false],
  ])('is claimable only once the target is reached and unclaimed (%#)', (patch, claimable) => {
    expect(isObjectiveClaimable(objective(patch))).toBe(claimable)
  })
})

describe('isRetiredStarter', () => {
  it.each([
    [{ category: 'starter' }, true],
    [{ category: 'starter', objective_type: 'collect' }, false],
    [{ category: 'daily' }, false],
  ])('flags a starter row only when it has no objective type (%#)', (patch, retired) => {
    expect(isRetiredStarter(objective(patch))).toBe(retired)
  })
})

it('takes equipment lessons to storage', () => {
  expect(objectiveActionPath(objective({ objective_type: 'equip' }), 'vault-1')).toBe(
    '/vault/vault-1/storage'
  )
})
