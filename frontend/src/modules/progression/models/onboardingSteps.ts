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

export interface SnapshotVault {
  bottle_caps: number
}

export interface SnapshotRoom {
  name: string
  base_cost: number
}

export interface SnapshotDweller {
  id: string
  age_group: string
  status: string
}

/**
 * A loaded snapshot the pure eligibility checks read. Eligibility never fetches,
 * queries the DOM, mutates, schedules or claims; it only inspects this snapshot.
 */
export interface TeachingSnapshot {
  vault: SnapshotVault | null
  buildableRooms: readonly SnapshotRoom[]
  dwellers: readonly SnapshotDweller[]
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
  /** Vault-relative path the action lives on; `''` is the vault home (construction). */
  route?: string
  /** Label for the fallback navigation action when no anchor is on screen. */
  routeLabel?: string
  /** Pure; `eligible` may highlight, `blocked`/`unknown` fall back to navigation. */
  eligibility: (snapshot: TeachingSnapshot) => TeachingEligibility
}

const OBJECTIVE_KEYS = {
  staffing: 'starter:assign a dweller correctly',
  housing: 'starter:build a living quarters',
  departure: 'starter:send a dweller exploring',
} as const

const MATURE_AGE_GROUPS = new Set(['adult', 'elder'])
const UNAVAILABLE_DEPARTURE_STATUSES = new Set(['exploring', 'questing', 'dead'])

const alwaysEligible = (): TeachingEligibility => 'eligible'

const hasObjective = (snapshot: TeachingSnapshot, templateKey: string): boolean =>
  snapshot.objectives.some((objective) => objective.template_key === templateKey)

const objectiveEligibility =
  (templateKey: string) =>
  (snapshot: TeachingSnapshot): TeachingEligibility =>
    hasObjective(snapshot, templateKey) ? 'eligible' : 'unknown'

const housingEligibility = (snapshot: TeachingSnapshot): TeachingEligibility => {
  if (!hasObjective(snapshot, OBJECTIVE_KEYS.housing)) return 'unknown'
  const room = snapshot.buildableRooms.find(
    (candidate) => candidate.name.trim().toLowerCase() === 'living room'
  )
  if (!room) return 'unknown'
  const caps = snapshot.vault?.bottle_caps ?? 0
  return caps >= room.base_cost
    ? 'eligible'
    : { blocked: `Not enough caps for Living Quarters (need ${room.base_cost})` }
}

const departureEligibility = (snapshot: TeachingSnapshot): TeachingEligibility => {
  if (!hasObjective(snapshot, OBJECTIVE_KEYS.departure)) return 'unknown'
  const available = snapshot.dwellers.some(
    (dweller) =>
      MATURE_AGE_GROUPS.has(dweller.age_group) &&
      !UNAVAILABLE_DEPARTURE_STATUSES.has(dweller.status)
  )
  return available ? 'eligible' : { blocked: 'No dweller is free to explore' }
}

/** The authored orientation arc; the only source of teaching order. */
export const ORIENTATION_STEPS: readonly OnboardingLesson[] = [
  {
    id: 'orientation.resources',
    kind: 'tap',
    title: 'Keep the power on',
    body: 'Power, food and water refill on their own. The bar shows what you have, its capacity, and whether you are gaining or draining.',
    anchors: ['resource-power'],
    eligibility: alwaysEligible,
  },
  {
    id: 'orientation.generator',
    kind: 'tap',
    title: 'Open the Power Generator',
    body: 'Every room runs on power. Its workers produce faster when their Strength fits the room; open it to see the current crew and output.',
    anchors: ['room-power'],
    eligibility: alwaysEligible,
  },
  {
    id: 'orientation.staffing',
    kind: 'inspection',
    title: 'Understand SPECIAL staffing',
    body: 'Each worker is strongest in one SPECIAL stat. Open Dwellers to review who matches their room; move someone only when a better slot is open.',
    templateKey: OBJECTIVE_KEYS.staffing,
    anchors: ['nav-dwellers'],
    route: 'dwellers',
    routeLabel: 'Open Dwellers',
    eligibility: objectiveEligibility(OBJECTIVE_KEYS.staffing),
  },
  {
    id: 'orientation.housing',
    kind: 'objective-explanation',
    title: 'Build more Living Quarters',
    body: 'Housing sets how many dwellers the vault can hold. Build another quarter to make room, and a new dweller will join.',
    templateKey: OBJECTIVE_KEYS.housing,
    anchors: ['build-living-room', 'build'],
    route: '',
    routeLabel: 'Open Vault',
    eligibility: housingEligibility,
  },
  {
    id: 'orientation.departure',
    kind: 'objective-explanation',
    title: 'Send a dweller exploring',
    body: 'An explorer brings back caps and loot. Pick a healthy adult, choose a short run, and check supplies before you confirm.',
    templateKey: OBJECTIVE_KEYS.departure,
    anchors: ['wasteland', 'nav-exploration'],
    route: 'exploration',
    routeLabel: 'Open Exploration',
    eligibility: departureEligibility,
  },
]
