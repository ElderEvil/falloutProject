import type { Objective } from './objective'

/**
 * Stable teaching IDs. These are the only keys persisted in the per-vault teaching
 * ledger; changing a lesson's wording never changes its ID.
 */
export type LessonId =
  | 'orientation.resources'
  | 'orientation.generator'
  | 'orientation.food'
  | 'orientation.diner'
  | 'orientation.water'
  | 'orientation.water-treatment'
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
    body: 'Power keeps the vault running. Watch this reserve and its production rate to see whether your supply is growing or draining. Next, meet the crew keeping the lights on.',
    anchors: ['resource-power'],
    eligibility: alwaysEligible,
  },
  {
    id: 'orientation.generator',
    kind: 'tap',
    title: 'Open the Power Generator',
    body: 'Open the generator to see its crew and output. Strength helps these workers produce power; other rooms use different SPECIAL stats. Next, check the food supply.',
    anchors: ['room-power'],
    eligibility: alwaysEligible,
  },
  {
    id: 'orientation.food',
    kind: 'tap',
    title: 'Keep your dwellers fed',
    body: 'Dwellers consume food over time. Watch this reserve and its production rate so you can act before supplies run low. Next, see where food is made.',
    anchors: ['resource-food'],
    eligibility: alwaysEligible,
  },
  {
    id: 'orientation.diner',
    kind: 'tap',
    title: 'Open the Diner',
    body: 'This room produces food. Agility helps its workers produce more, so match agile dwellers to the kitchen. Next, check your water supply.',
    anchors: ['room-food'],
    route: '',
    routeLabel: 'Open Vault',
    eligibility: alwaysEligible,
  },
  {
    id: 'orientation.water',
    kind: 'tap',
    title: 'Keep clean water flowing',
    body: 'Dwellers consume water over time. Keep an eye on this reserve and its production rate to avoid a shortage. Next, meet the water treatment crew.',
    anchors: ['resource-water'],
    eligibility: alwaysEligible,
  },
  {
    id: 'orientation.water-treatment',
    kind: 'tap',
    title: 'Open Water Treatment',
    body: 'This room produces clean water. Perception helps its workers produce more. Next, review your crew and compare their SPECIAL with their jobs.',
    anchors: ['room-water'],
    route: '',
    routeLabel: 'Open Vault',
    eligibility: alwaysEligible,
  },
  {
    id: 'orientation.staffing',
    kind: 'inspection',
    title: 'Understand SPECIAL staffing',
    body: 'Open Dwellers and compare a worker’s SPECIAL with their room. Your starting crew is already matched, so there is no need to move anyone just for the guide. Next, make room for a newcomer.',
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
    body: 'Open Build and choose Living room, then select a highlighted empty slot beside an existing room or elevator. The new segment raises capacity and may merge with existing quarters. Claim this objective’s reward to welcome a new dweller immediately, then review them before exploring.',
    templateKeys: OBJECTIVE_KEYS.housing,
    anchors: ['build-living-room-slot', 'build-living-room', 'build'],
    route: '',
    routeLabel: 'Open Vault',
    eligibility: housingEligibility,
  },
  {
    id: 'orientation.departure',
    kind: 'objective-explanation',
    title: 'Send a dweller exploring',
    body: 'Your newcomer is an option if they are healthy and available. Review equipment, supplies and the run length before sending an adult out. Sending a worker leaves their production room short; the guide will suggest something useful to do while they are away.',
    templateKeys: OBJECTIVE_KEYS.departure,
    anchors: ['wasteland', 'nav-exploration'],
    route: 'exploration',
    routeLabel: 'Open Exploration',
    eligibility: departureEligibility,
  },
]
