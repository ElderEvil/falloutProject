import { describe, expect, it } from 'vitest'
import {
  ORIENTATION_STEPS,
  type OnboardingLesson,
  type TeachingSnapshot,
} from '@/modules/progression/models/onboardingSteps'
import type { Objective } from '@/modules/progression/models/objective'

const EMPTY_SNAPSHOT: TeachingSnapshot = {
  vault: null,
  buildableRooms: [],
  builtRooms: [],
  dwellers: [],
  dwellersLoaded: false,
  objectives: [],
  activeRuns: [],
  lessons: {},
}

const objectiveWithKey = (templateKey: string): Objective =>
  ({ template_key: templateKey }) as Objective

const snapshotWith = (overrides: Partial<TeachingSnapshot>): TeachingSnapshot => ({
  ...EMPTY_SNAPSHOT,
  ...overrides,
})

const byId = new Map<OnboardingLesson['id'], OnboardingLesson>(
  ORIENTATION_STEPS.map((step) => [step.id, step] as const)
)

const STAFFING = 'starter:assign a dweller correctly'
const HOUSING = 'starter:build a living quarters'
const DEPARTURE = 'starter:send a dweller exploring'

const LIVING_ROOM = {
  name: 'Living room',
  category: 'Capacity',
  base_cost: 100,
  incremental_cost: 25,
}
const SEEDED_CAPACITY_ROOMS = [{ category: 'Capacity' }, { category: 'Capacity' }]

describe('onboardingSteps', () => {
  it('authors the five orientation lessons in order with stable ids', () => {
    expect(ORIENTATION_STEPS.map((step) => step.id)).toEqual([
      'orientation.resources',
      'orientation.generator',
      'orientation.staffing',
      'orientation.housing',
      'orientation.departure',
    ])
  })

  it('links only the objective-backed lessons to server template keys', () => {
    expect(byId.get('orientation.resources')?.templateKey).toBeUndefined()
    expect(byId.get('orientation.generator')?.templateKey).toBeUndefined()
    expect(byId.get('orientation.staffing')?.templateKey).toBe(STAFFING)
    expect(byId.get('orientation.housing')?.templateKey).toBe(HOUSING)
    expect(byId.get('orientation.departure')?.templateKey).toBe(DEPARTURE)
  })

  it('anchors each lesson to a real data-onboarding target', () => {
    expect(byId.get('orientation.resources')?.anchors).toContain('resource-power')
    expect(byId.get('orientation.generator')?.anchors).toContain('room-power')
    expect(byId.get('orientation.staffing')?.anchors).toContain('nav-dwellers')
    expect(byId.get('orientation.housing')?.anchors).toContain('build-living-room')
    expect(byId.get('orientation.departure')?.anchors).toEqual(
      expect.arrayContaining(['wasteland', 'nav-exploration'])
    )
  })

  it('gives housing a fallback route back to construction', () => {
    expect(byId.get('orientation.housing')?.route).toBe('')
    expect(byId.get('orientation.housing')?.routeLabel).toBe('Open Vault')
  })

  it('always marks the tap lessons eligible', () => {
    expect(byId.get('orientation.resources')?.eligibility(EMPTY_SNAPSHOT)).toBe('eligible')
    expect(byId.get('orientation.generator')?.eligibility(EMPTY_SNAPSHOT)).toBe('eligible')
  })

  it('holds objective-backed lessons unknown until their objective is loaded', () => {
    expect(byId.get('orientation.staffing')?.eligibility(EMPTY_SNAPSHOT)).toBe('unknown')
    expect(byId.get('orientation.housing')?.eligibility(EMPTY_SNAPSHOT)).toBe('unknown')
    expect(byId.get('orientation.departure')?.eligibility(EMPTY_SNAPSHOT)).toBe('unknown')
  })

  it('marks staffing eligible once its objective loads', () => {
    const loaded = snapshotWith({ objectives: [objectiveWithKey(STAFFING)] })
    expect(byId.get('orientation.staffing')?.eligibility(loaded)).toBe('eligible')
  })

  it('prices housing from catalog cost plus a per-existing-room increment', () => {
    const snapshot = snapshotWith({
      vault: { bottle_caps: 125 },
      buildableRooms: [LIVING_ROOM],
      builtRooms: SEEDED_CAPACITY_ROOMS,
      objectives: [objectiveWithKey(HOUSING)],
    })
    expect(byId.get('orientation.housing')?.eligibility(snapshot)).toEqual({
      blocked: 'Not enough caps for Living Quarters (need 150)',
    })
  })

  it('marks housing eligible once the raised price is affordable', () => {
    const snapshot = snapshotWith({
      vault: { bottle_caps: 200 },
      buildableRooms: [LIVING_ROOM],
      builtRooms: SEEDED_CAPACITY_ROOMS,
      objectives: [objectiveWithKey(HOUSING)],
    })
    expect(byId.get('orientation.housing')?.eligibility(snapshot)).toBe('eligible')
  })

  it('keeps housing unknown until the built rooms are loaded', () => {
    const snapshot = snapshotWith({
      vault: { bottle_caps: 9999 },
      buildableRooms: [LIVING_ROOM],
      builtRooms: [],
      objectives: [objectiveWithKey(HOUSING)],
    })
    expect(byId.get('orientation.housing')?.eligibility(snapshot)).toBe('unknown')
  })

  it('keeps departure unknown until the roster is loaded', () => {
    const snapshot = snapshotWith({
      objectives: [objectiveWithKey(DEPARTURE)],
      dwellersLoaded: false,
      dwellers: [{ id: 'a', age_group: 'adult', status: 'resting', health: 50 }],
    })
    expect(byId.get('orientation.departure')?.eligibility(snapshot)).toBe('unknown')
  })

  it('offers the matching remedy for each departure blocker', () => {
    const objectives = [objectiveWithKey(DEPARTURE)]
    const noAdult = snapshotWith({
      objectives,
      dwellersLoaded: true,
      dwellers: [{ id: 'c', age_group: 'child', status: 'idle', health: 50 }],
    })
    expect(byId.get('orientation.departure')?.eligibility(noAdult)).toEqual({
      blocked: 'Grow the vault to send an adult out',
    })

    const away = snapshotWith({
      objectives,
      dwellersLoaded: true,
      dwellers: [{ id: 'a', age_group: 'adult', status: 'exploring', health: 50 }],
    })
    expect(byId.get('orientation.departure')?.eligibility(away)).toEqual({
      blocked: 'Your dwellers are away; they will return soon',
    })

    const wounded = snapshotWith({
      objectives,
      dwellersLoaded: true,
      dwellers: [{ id: 'a', age_group: 'adult', status: 'resting', health: 0 }],
    })
    expect(byId.get('orientation.departure')?.eligibility(wounded)).toEqual({
      blocked: 'Treat a wounded dweller before sending them out',
    })
  })

  it('marks departure eligible for a healthy mature dweller', () => {
    const snapshot = snapshotWith({
      objectives: [objectiveWithKey(DEPARTURE)],
      dwellersLoaded: true,
      dwellers: [{ id: 'a', age_group: 'adult', status: 'resting', health: 50 }],
    })
    expect(byId.get('orientation.departure')?.eligibility(snapshot)).toBe('eligible')
  })
})
