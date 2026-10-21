import type { Objective } from './objective'
import { getRoomSegmentCount } from '@/modules/rooms/utils/room'
import type { Room } from '@/modules/rooms/models/room'

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
  | 'orientation.preparation'
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

export interface SnapshotBuiltRoom extends Pick<Room, 'name' | 'size' | 'size_min'> {
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

// Match the build menu: incremental cost is per segment of the same room type.
const livingQuartersPrice = (snapshot: TeachingSnapshot): number | undefined => {
  const template = snapshot.buildableRooms.find(
    (candidate) => candidate.name.trim().toLowerCase() === 'living room'
  )
  if (!template || typeof template.incremental_cost !== 'number') return undefined
  if (!snapshot.roomsLoaded) return undefined
  const existing = snapshot.builtRooms
    .filter((room) => room.name === template.name)
    .reduce((count, room) => count + getRoomSegmentCount(room), 0)
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
    body: 'Power, food and water keep your vault alive. Watch their reserves and net rates.',
    anchors: ['resource-power'],
    eligibility: alwaysEligible,
  },
  {
    id: 'orientation.generator',
    kind: 'tap',
    title: 'Open the Power Generator',
    body: 'Open the generator to inspect workers and output. Strength boosts power production.',
    anchors: ['room-power'],
    route: '',
    routeLabel: 'Open Vault',
    eligibility: alwaysEligible,
  },
  {
    id: 'orientation.staffing',
    kind: 'inspection',
    title: 'Understand SPECIAL staffing',
    body: 'Open Dwellers. Match SPECIAL to the job: Strength for power, Agility for food, Perception for water. Your crew already fits.',
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
    body: 'Open Build. Choose Living room, then a highlighted empty slot. Claim your reward to welcome a newcomer.',
    templateKeys: OBJECTIVE_KEYS.housing,
    anchors: ['build-living-room-slot', 'build-living-room', 'build'],
    route: '',
    routeLabel: 'Open Vault',
    eligibility: housingEligibility,
  },
  {
    id: 'orientation.preparation',
    kind: 'inspection',
    title: 'Prepare your explorer',
    body: 'Open a healthy adult in Dwellers. Equip a weapon and outfit before sending them out.',
    anchors: ['dweller-equipment', 'nav-dwellers'],
    route: 'dwellers',
    routeLabel: 'Open Dwellers',
    eligibility: departureEligibility,
  },
  {
    id: 'orientation.departure',
    kind: 'objective-explanation',
    title: 'Drag a dweller to the wasteland',
    body: 'Drag a healthy adult from Unassigned onto The Wasteland. Dropping opens preparation; it does not send them yet.',
    templateKeys: OBJECTIVE_KEYS.departure,
    anchors: ['exploration-dweller', 'wasteland'],
    route: '',
    routeLabel: 'Open Vault',
    eligibility: departureEligibility,
  },
]
