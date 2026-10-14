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
  category: string
  base_cost: number
  incremental_cost?: number | null
}

export interface SnapshotBuiltRoom {
  category: string
}

export interface SnapshotDweller {
  id: string
  age_group: string
  status: string
  health: number
}

/**
 * A loaded snapshot the pure eligibility checks read. Eligibility never fetches,
 * queries the DOM, mutates, schedules or claims; it only inspects this snapshot.
 * Absent data must read as `unknown`, never as an empty-but-valid state.
 */
export interface TeachingSnapshot {
  vault: SnapshotVault | null
  buildableRooms: readonly SnapshotRoom[]
  builtRooms: readonly SnapshotBuiltRoom[]
  roomsLoaded: boolean
  dwellers: readonly SnapshotDweller[]
  dwellersLoaded: boolean
  objectives: readonly Objective[]
}

export interface OnboardingLesson {
  id: LessonId
  kind: LessonKind
  title: string
  body: string
  templateKeys?: readonly string[]
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
  staffing: ['starter:assign a dweller correctly#v2', 'starter:assign a dweller correctly'],
  housing: ['starter:build a living quarters#v2', 'starter:build a living quarters'],
  departure: ['starter:send a dweller exploring'],
} as const

const MATURE_AGE_GROUPS = new Set(['adult', 'elder'])
const AWAY_STATUSES = new Set(['exploring', 'questing'])
const UNAVAILABLE_DEPARTURE_STATUSES = new Set(['exploring', 'questing', 'dead'])

const alwaysEligible = (): TeachingEligibility => 'eligible'

const hasObjective = (snapshot: TeachingSnapshot, templateKeys: readonly string[]): boolean =>
  snapshot.objectives.some(
    (objective) => objective.template_key != null && templateKeys.includes(objective.template_key)
  )

const objectiveEligibility =
  (templateKeys: readonly string[]) =>
  (snapshot: TeachingSnapshot): TeachingEligibility =>
    hasObjective(snapshot, templateKeys) ? 'eligible' : 'unknown'

const isMature = (dweller: SnapshotDweller): boolean => MATURE_AGE_GROUPS.has(dweller.age_group)

const canDepart = (dweller: SnapshotDweller): boolean =>
  isMature(dweller) && !UNAVAILABLE_DEPARTURE_STATUSES.has(dweller.status) && dweller.health > 0

// Mirrors backend get_room_build_price: catalog cost plus an increment per existing room
// in the same category, so an already-built vault raises the next Living Quarters above base.
const livingQuartersPrice = (snapshot: TeachingSnapshot): number | undefined => {
  const template = snapshot.buildableRooms.find(
    (candidate) => candidate.name.trim().toLowerCase() === 'living room'
  )
  if (!template || typeof template.incremental_cost !== 'number') return undefined
  if (!snapshot.roomsLoaded) return undefined
  const category = template.category.trim().toLowerCase()
  const existing = snapshot.builtRooms.filter(
    (room) => room.category.trim().toLowerCase() === category
  ).length
  return template.base_cost + existing * template.incremental_cost
}

const housingEligibility = (snapshot: TeachingSnapshot): TeachingEligibility => {
  if (!hasObjective(snapshot, OBJECTIVE_KEYS.housing)) return 'unknown'
  const price = livingQuartersPrice(snapshot)
  if (price === undefined) return 'unknown'
  const caps = snapshot.vault?.bottle_caps ?? 0
  return caps >= price
    ? 'eligible'
    : { blocked: `Not enough caps for Living Quarters (need ${price})` }
}

const departureEligibility = (snapshot: TeachingSnapshot): TeachingEligibility => {
  if (!hasObjective(snapshot, OBJECTIVE_KEYS.departure)) return 'unknown'
  if (!snapshot.dwellersLoaded) return 'unknown'
  const mature = snapshot.dwellers.filter(isMature)
  if (mature.length === 0) return { blocked: 'Grow the vault to send an adult out' }
  if (mature.some(canDepart)) return 'eligible'
  if (mature.every((dweller) => AWAY_STATUSES.has(dweller.status))) {
    return { blocked: 'Your dwellers are away; they will return soon' }
  }
  if (mature.some((dweller) => dweller.health <= 0)) {
    return { blocked: 'Treat a wounded dweller before sending them out' }
  }
  return { blocked: 'No dweller is free to explore' }
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
    templateKeys: OBJECTIVE_KEYS.staffing,
    anchors: ['nav-dwellers'],
    route: 'dwellers',
    routeLabel: 'Open Dwellers',
    eligibility: objectiveEligibility(OBJECTIVE_KEYS.staffing),
  },
  {
    id: 'orientation.housing',
    kind: 'objective-explanation',
    title: 'Build more Living Quarters',
    body: 'Housing sets how many dwellers the vault can hold. Build another quarter to make room for more arrivals.',
    templateKeys: OBJECTIVE_KEYS.housing,
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
    templateKeys: OBJECTIVE_KEYS.departure,
    anchors: ['wasteland', 'nav-exploration'],
    route: 'exploration',
    routeLabel: 'Open Exploration',
    eligibility: departureEligibility,
  },
]
