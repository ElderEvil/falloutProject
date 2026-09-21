import { describe, it, expect } from 'vitest'
import {
  PROGRESSION_SURFACES,
  progressionSurfaceFor,
  type ProgressionSurface,
} from '@/modules/vault/components/shell/progressionSurfaces'

/**
 * Progression visibility red line (`docs/backend/GAME_MECHANICS.md`).
 *
 * Level-up, loot, training completion, and quest/objective completion must
 * surface beyond the notification bell. This pins the matrix that decides it, so
 * a new progression flow cannot ship notification-only by omission.
 */
describe('progression surfaces matrix', () => {
  it('surfaces every progression event the red line names', () => {
    const required: Record<string, ProgressionSurface> = {
      level_up: 'toast',
      exploration_complete: 'toast', // loot
      training_complete: 'toast',
      quest_complete: 'toast',
      achievement_unlocked: 'toast', // objective completion
    }

    for (const [type, surface] of Object.entries(required)) {
      expect(progressionSurfaceFor(type), `${type} must surface beyond the bell`).toBe(surface)
    }
  })

  it('keeps the pre-existing hazard team join surface', () => {
    expect(progressionSurfaceFor('hazard_team_joined')).toBe('toast')
  })

  it('leaves informational events bell-only', () => {
    const informational = [
      'resource_low',
      'resource_critical',
      'power_outage',
      'combat_started',
      'dweller_injured',
      'exploration_update',
      'map_registration_failed',
      'radio_new_dweller',
    ]

    for (const type of informational) {
      expect(progressionSurfaceFor(type), `${type} should stay bell-only`).toBeNull()
    }
  })

  it('returns null for an unknown notification type', () => {
    expect(progressionSurfaceFor('something_new')).toBeNull()
  })

  it('exposes only toast surfaces today', () => {
    expect(Object.values(PROGRESSION_SURFACES).every((surface) => surface === 'toast')).toBe(true)
  })
})
