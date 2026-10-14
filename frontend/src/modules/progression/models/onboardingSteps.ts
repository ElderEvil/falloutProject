import type { Objective } from './objective'

/**
 * Stable teaching IDs. These are the only keys persisted in the per-vault teaching
 * ledger; changing a lesson's wording never changes its ID.
 */
export type LessonId =
  | 'orientation.resources'
  | 'orientation.generator'
  | 'orientation.staffing'
  | 'orientation.housing'
  | 'orientation.departure'

/** How a lesson is presented and acknowledged. */
export type LessonKind = 'tap' | 'inspection' | 'objective-explanation'

/** Result of a pure eligibility check. */
export type TeachingEligibility = 'eligible' | 'unknown' | { blocked: string }

/**
 * A loaded snapshot the pure eligibility checks read. Eligibility never fetches,
 * queries the DOM, mutates, schedules or claims; it only inspects this snapshot.
 * Collection member types stay loose until the checks are wired.
 */
export interface TeachingSnapshot {
  vault: unknown
  rooms: readonly unknown[]
  dwellers: readonly unknown[]
  objectives: readonly Objective[]
  activeRuns: readonly unknown[]
  lessons: Readonly<Partial<Record<LessonId, 'acknowledged' | 'skipped'>>>
}

export interface OnboardingLesson {
  id: LessonId
  kind: LessonKind
  title: string
  body: string
  /** Server objective `template_key` this lesson explains, when objective-backed. */
  templateKey?: string
  /** `data-onboarding` anchors on the relevant screen; first present wins. */
  anchors?: string[]
  /** Vault-relative path the action lives on; omit when it is on the vault home. */
  route?: string
  /** Pure; returns 'unknown' until the concrete checks are wired. */
  eligibility: (snapshot: TeachingSnapshot) => TeachingEligibility
}

const unknownEligibility = (): TeachingEligibility => 'unknown'

/**
 * The authored orientation arc. This list is the only source of teaching order;
 * the backend catalog remains the only source of reward order and payouts.
 */
export const ORIENTATION_STEPS: readonly OnboardingLesson[] = [
  {
    id: 'orientation.resources',
    kind: 'tap',
    title: 'Keep the power on',
    body: 'Power, food and water refill on their own. The bar shows what you have, its capacity, and whether you are gaining or draining.',
    anchors: ['resource-power'],
    eligibility: unknownEligibility,
  },
  {
    id: 'orientation.generator',
    kind: 'tap',
    title: 'Open the Power Generator',
    body: 'Every room runs on power. Its workers produce faster when their Strength fits the room; open it to see the current crew and output.',
    anchors: ['room-power'],
    eligibility: unknownEligibility,
  },
  {
    id: 'orientation.staffing',
    kind: 'inspection',
    title: 'Understand SPECIAL staffing',
    body: 'Each worker is strongest in one SPECIAL stat. Open Dwellers to review who matches their room; move someone only when a better slot is open.',
    templateKey: 'starter:assign a dweller correctly',
    anchors: ['nav-dwellers'],
    route: 'dwellers',
    eligibility: unknownEligibility,
  },
  {
    id: 'orientation.housing',
    kind: 'objective-explanation',
    title: 'Build more Living Quarters',
    body: 'Housing sets how many dwellers the vault can hold. Build another quarter to make room, and a new dweller will join.',
    templateKey: 'starter:build a living quarters',
    anchors: ['build-living-room', 'build'],
    eligibility: unknownEligibility,
  },
  {
    id: 'orientation.departure',
    kind: 'objective-explanation',
    title: 'Send a dweller exploring',
    body: 'An explorer brings back caps and loot. Pick a healthy adult, choose a short run, and check supplies before you confirm.',
    templateKey: 'starter:send a dweller exploring',
    anchors: ['wasteland', 'nav-exploration'],
    route: 'exploration',
    eligibility: unknownEligibility,
  },
]
