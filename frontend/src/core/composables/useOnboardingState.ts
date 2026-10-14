import { ref, type Ref } from 'vue'
import { useStorage } from '@vueuse/core'

/** Whole-tour flags the existing guide reads. */
export interface OnboardingState {
  skipped?: boolean
  welcomed?: boolean
  created?: boolean
}

export type LessonStatus = 'acknowledged' | 'skipped'

/**
 * Per-vault teaching ledger. Lesson IDs are stable strings owned by the
 * progression module's authored definition list; a missing ID means unseen.
 * Contextual-mechanic/hint state is intentionally out of scope for the first release.
 */
export interface TeachingState {
  version: 1
  lessons: Partial<Record<string, LessonStatus>>
  replayOrientation: boolean
}

/** Persisted shape of one vault's onboarding record. */
export interface VaultOnboardingRecord extends OnboardingState {
  teaching?: TeachingState
}

type Records = Record<string, VaultOnboardingRecord>

const STORAGE_KEY = 'onboarding:v1'

function usableStorage(): Storage | null {
  try {
    const probe = '__onboarding_probe__'
    window.localStorage.setItem(probe, '1')
    window.localStorage.removeItem(probe)
    return window.localStorage
  } catch {
    return null
  }
}

let sharedState: Ref<Records | undefined> | undefined

// One state for every consumer for the whole session. It is created on first use and
// never replaced, so a storage failure after start-up keeps the running session instead
// of handing late consumers a divergent, empty copy.
function onboardingState(): Ref<Records | undefined> {
  if (sharedState) return sharedState
  const storage = usableStorage()
  sharedState = storage ? useStorage<Records>(STORAGE_KEY, {}, storage) : ref<Records>({})
  return sharedState
}

function emptyTeaching(): TeachingState {
  return { version: 1, lessons: {}, replayOrientation: false }
}

function isLessonStatus(value: unknown): value is LessonStatus {
  return value === 'acknowledged' || value === 'skipped'
}

function normalizeTeaching(value: unknown): TeachingState {
  if (!value || typeof value !== 'object') return emptyTeaching()
  const record = value as { version?: unknown; lessons?: unknown; replayOrientation?: unknown }
  if (record.version !== 1) return emptyTeaching()
  const safeLessons: Record<string, LessonStatus> = {}
  const lessons = record.lessons
  if (lessons && typeof lessons === 'object' && !Array.isArray(lessons)) {
    for (const [lessonId, status] of Object.entries(lessons)) {
      if (isLessonStatus(status)) safeLessons[lessonId] = status
    }
  }
  return { version: 1, lessons: safeLessons, replayOrientation: record.replayOrientation === true }
}

/**
 * Per-vault onboarding state. Objective progress and rewards stay server-side; this
 * only tracks the welcome/skip flags and the per-lesson teaching ledger for each vault.
 * Corrupt or unavailable local data degrades to an empty ledger without breaking render.
 */
export function useOnboardingState() {
  const state = onboardingState()

  const records = (): Records => {
    const value: unknown = state.value
    return value && typeof value === 'object' && !Array.isArray(value) ? (value as Records) : {}
  }

  const readRecord = (vaultId: string | null | undefined): VaultOnboardingRecord =>
    vaultId ? (records()[vaultId] ?? {}) : {}

  const write = (vaultId: string, next: VaultOnboardingRecord): void => {
    state.value = { ...records(), [vaultId]: next }
  }

  const vaultState = (vaultId: string | null | undefined): OnboardingState => readRecord(vaultId)

  const patch = (vaultId: string | null | undefined, next: Partial<OnboardingState>): void => {
    if (!vaultId) return
    write(vaultId, { ...readRecord(vaultId), ...next })
  }

  const reset = (vaultId: string | null | undefined): void => {
    if (!vaultId || !(vaultId in records())) return
    const next = { ...records() }
    delete next[vaultId]
    state.value = next
  }

  const resetAll = (): void => {
    state.value = {}
  }

  /** Read-only view of the teaching ledger; never persists a default. */
  const teaching = (vaultId: string | null | undefined): TeachingState =>
    normalizeTeaching(readRecord(vaultId).teaching)

  const setLessonStatus = (
    vaultId: string | null | undefined,
    lessonId: string,
    status: LessonStatus
  ): void => {
    if (!vaultId) return
    const current = teaching(vaultId)
    write(vaultId, {
      ...readRecord(vaultId),
      teaching: { ...current, lessons: { ...current.lessons, [lessonId]: status } },
    })
  }

  /** Player deliberately reviewed/continued a lesson. */
  const acknowledgeLesson = (vaultId: string | null | undefined, lessonId: string): void =>
    setLessonStatus(vaultId, lessonId, 'acknowledged')

  /** Player skipped this explanation; the server objective and reward stay untouched. */
  const skipLesson = (vaultId: string | null | undefined, lessonId: string): void =>
    setLessonStatus(vaultId, lessonId, 'skipped')

  /** Whole-tour skip; preserves individual lesson history. */
  const skipTour = (vaultId: string | null | undefined): void => patch(vaultId, { skipped: true })

  /** Clear whole-tour suppression only; individual skipped lessons stay skipped. */
  const resumeGuide = (vaultId: string | null | undefined): void => patch(vaultId, { skipped: false })

  /** Clear orientation teaching statuses and re-arm the tour without touching server state. */
  const replayOrientation = (vaultId: string | null | undefined): void => {
    if (!vaultId) return
    write(vaultId, {
      ...readRecord(vaultId),
      skipped: false,
      teaching: { ...emptyTeaching(), replayOrientation: true },
    })
  }

  return {
    state,
    vaultState,
    patch,
    reset,
    resetAll,
    teaching,
    acknowledgeLesson,
    skipLesson,
    skipTour,
    resumeGuide,
    replayOrientation,
  }
}
