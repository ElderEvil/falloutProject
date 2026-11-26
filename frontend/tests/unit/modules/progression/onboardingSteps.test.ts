import { describe, expect, it } from 'vite-plus/test'
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
  roomsLoaded: false,
  dwellers: [],
  dwellersLoaded: false,
  objectives: [],
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

const eligibility = (id: OnboardingLesson['id'], snapshot: TeachingSnapshot) =>
  byId.get(id)?.eligibility(snapshot)

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

/** Housing priced from the catalog: 100 base + 25 per already-built capacity room. */
const housingSnapshot = (
  bottle_caps: number,
  { roomsLoaded = true, builtRooms = SEEDED_CAPACITY_ROOMS } = {}
): TeachingSnapshot =>
  snapshotWith({
    vault: { bottle_caps },
    buildableRooms: [LIVING_ROOM],
    builtRooms,
    roomsLoaded,
    objectives: [objectiveWithKey(HOUSING)],
  })

const departureSnapshot = (dwellers: TeachingSnapshot['dwellers'], dwellersLoaded = true) =>
  snapshotWith({ objectives: [objectiveWithKey(DEPARTURE)], dwellers, dwellersLoaded })

describe('onboardingSteps', () => {
  it('keeps stable teaching ids and prepares equipment before departure', () => {
    expect(ORIENTATION_STEPS.map((step) => step.id)).toEqual([
      'orientation.resources',
      'orientation.generator',
      'orientation.staffing',
      'orientation.housing',
      'orientation.weapon',
      'orientation.outfit',
      'orientation.departure',
    ])
  })

  it('links only the objective-backed lessons to server template keys', () => {
    expect(byId.get('orientation.resources')?.templateKeys).toBeUndefined()
    expect(byId.get('orientation.generator')?.templateKeys).toBeUndefined()
    expect(byId.get('orientation.staffing')?.templateKeys).toEqual([
      `${STAFFING}#v3`,
      `${STAFFING}#v2`,
      STAFFING,
    ])
    expect(byId.get('orientation.housing')?.templateKeys).toEqual([
      `${HOUSING}#v3`,
      `${HOUSING}#v2`,
      HOUSING,
    ])
    expect(byId.get('orientation.departure')?.templateKeys).toEqual([`${DEPARTURE}#v3`, DEPARTURE])
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
    expect(eligibility('orientation.resources', EMPTY_SNAPSHOT)).toBe('eligible')
    expect(eligibility('orientation.generator', EMPTY_SNAPSHOT)).toBe('eligible')
  })

  it('holds objective-backed lessons unknown until their objective is loaded', () => {
    for (const id of [
      'orientation.staffing',
      'orientation.housing',
      'orientation.departure',
    ] as const) {
      expect(eligibility(id, EMPTY_SNAPSHOT)).toBe('unknown')
    }
    const loaded = snapshotWith({ objectives: [objectiveWithKey(STAFFING)] })
    expect(eligibility('orientation.staffing', loaded)).toBe('eligible')
  })

  it.each([
    // 100 base + 25 per built capacity room: two rooms put the price at 150.
    [125, {}, { blocked: 'Not enough caps for Living Quarters (need 150)' }],
    [200, {}, 'eligible'],
    [9999, { roomsLoaded: false, builtRooms: [] }, 'unknown'],
    [9999, { builtRooms: [] }, 'eligible'], // A loaded, empty vault is a valid zero-room state.
  ])('prices and gates housing from the catalog and loaded rooms (%#)', (caps, opts, expected) => {
    expect(eligibility('orientation.housing', housingSnapshot(caps, opts))).toEqual(expected)
  })

  it('keeps departure unknown until the roster is loaded', () => {
    const snapshot = departureSnapshot(
      [{ id: 'a', age_group: 'adult', status: 'resting', health: 50 }],
      false
    )
    expect(eligibility('orientation.departure', snapshot)).toBe('unknown')
  })

  it.each([
    [
      [{ id: 'c', age_group: 'child', status: 'idle', health: 50 }],
      'Grow the vault to send an adult out',
    ],
    [
      [{ id: 'a', age_group: 'adult', status: 'exploring', health: 50 }],
      'Your dwellers are away; they will return soon',
    ],
    [
      [{ id: 'a', age_group: 'adult', status: 'resting', health: 0 }],
      'Treat a wounded dweller before sending them out',
    ],
  ])('offers the matching remedy for each departure blocker (%#)', (dwellers, blocked) => {
    expect(eligibility('orientation.departure', departureSnapshot(dwellers))).toEqual({ blocked })
  })

  it('marks departure eligible for a healthy mature dweller', () => {
    const snapshot = departureSnapshot([
      { id: 'a', age_group: 'adult', status: 'resting', health: 50 },
    ])
    expect(eligibility('orientation.departure', snapshot)).toBe('eligible')
  })
})
