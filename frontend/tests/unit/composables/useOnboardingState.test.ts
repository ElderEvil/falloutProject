import { beforeEach, describe, expect, it } from 'vitest'
import { useOnboardingState } from '@/core/composables/useOnboardingState'

const EMPTY_TEACHING = { version: 1, lessons: {}, replayOrientation: false }

describe('useOnboardingState', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('tracks welcomed and skipped per vault', () => {
    const { patch, vaultState } = useOnboardingState()
    patch('v1', { welcomed: true })
    patch('v1', { skipped: true })
    expect(vaultState('v1')).toEqual({ welcomed: true, skipped: true })
    expect(vaultState('v2')).toEqual({})
  })

  it('re-arms a skipped vault', () => {
    const { patch, reset, vaultState } = useOnboardingState()
    patch('v1', { skipped: true })
    reset('v1')
    expect(vaultState('v1')).toEqual({})
  })

  it('ignores a missing vault id', () => {
    const { patch, reset, vaultState } = useOnboardingState()
    patch(null, { skipped: true })
    reset(null)
    expect(vaultState(null)).toEqual({})
  })

  it('clears every vault', () => {
    const { patch, resetAll, vaultState } = useOnboardingState()
    patch('v1', { skipped: true })
    patch('v2', { skipped: true })
    resetAll()
    expect(vaultState('v1')).toEqual({})
    expect(vaultState('v2')).toEqual({})
  })

  it('reads an empty teaching ledger for an unseen vault', () => {
    const { teaching } = useOnboardingState()
    expect(teaching('v1')).toEqual(EMPTY_TEACHING)
  })

  it('records lesson acknowledgements and skips without touching whole-tour flags', () => {
    const { acknowledgeLesson, skipLesson, teaching, vaultState } = useOnboardingState()
    acknowledgeLesson('v1', 'orientation.resources')
    skipLesson('v1', 'orientation.generator')
    expect(teaching('v1').lessons).toEqual({
      'orientation.resources': 'acknowledged',
      'orientation.generator': 'skipped',
    })
    expect(vaultState('v1').skipped).toBeUndefined()
  })

  it('skipTour sets whole-tour suppression but preserves lesson history', () => {
    const { acknowledgeLesson, skipTour, teaching, vaultState } = useOnboardingState()
    acknowledgeLesson('v1', 'orientation.resources')
    skipTour('v1')
    expect(vaultState('v1').skipped).toBe(true)
    expect(teaching('v1').lessons).toEqual({ 'orientation.resources': 'acknowledged' })
  })

  it('resumeGuide clears only whole-tour suppression', () => {
    const { skipLesson, skipTour, resumeGuide, teaching, vaultState } = useOnboardingState()
    skipLesson('v1', 'orientation.housing')
    skipTour('v1')
    resumeGuide('v1')
    expect(vaultState('v1').skipped).toBe(false)
    expect(teaching('v1').lessons).toEqual({ 'orientation.housing': 'skipped' })
  })

  it('replayOrientation clears lessons and suppression but keeps the creation marker', () => {
    const { acknowledgeLesson, replayOrientation, teaching, patch, vaultState } = useOnboardingState()
    patch('v1', { created: true, welcomed: true })
    acknowledgeLesson('v1', 'orientation.resources')
    replayOrientation('v1')
    expect(teaching('v1')).toEqual({ version: 1, lessons: {}, replayOrientation: true })
    expect(vaultState('v1')).toMatchObject({ created: true, welcomed: true, skipped: false })
  })

  it('isolates teaching state per vault', () => {
    const { acknowledgeLesson, teaching } = useOnboardingState()
    acknowledgeLesson('v1', 'orientation.resources')
    expect(teaching('v1').lessons).toEqual({ 'orientation.resources': 'acknowledged' })
    expect(teaching('v2').lessons).toEqual({})
  })

  it('migrates a legacy record lazily without losing its flags', () => {
    localStorage.setItem(
      'onboarding:v1',
      JSON.stringify({ v1: { created: true, welcomed: true, skipped: true } })
    )
    const { teaching, vaultState } = useOnboardingState()
    expect(vaultState('v1')).toEqual({ created: true, welcomed: true, skipped: true })
    expect(teaching('v1')).toEqual(EMPTY_TEACHING)
  })

  it('rejects an unsupported teaching version instead of coercing it', () => {
    localStorage.setItem(
      'onboarding:v1',
      JSON.stringify({
        v1: {
          teaching: {
            version: 2,
            lessons: { 'orientation.resources': 'acknowledged' },
            replayOrientation: false,
          },
        },
      })
    )
    const { teaching } = useOnboardingState()
    expect(teaching('v1')).toEqual(EMPTY_TEACHING)
  })

  it('retains only acknowledged/skipped lesson statuses from persisted data', () => {
    localStorage.setItem(
      'onboarding:v1',
      JSON.stringify({
        v1: {
          teaching: {
            version: 1,
            lessons: {
              'orientation.resources': 'acknowledged',
              'orientation.housing': 'completed',
              rogue: 7,
            },
            replayOrientation: false,
          },
        },
      })
    )
    const { teaching } = useOnboardingState()
    expect(teaching('v1').lessons).toEqual({ 'orientation.resources': 'acknowledged' })
  })

  it('survives corrupt storage and keeps working from memory', () => {
    localStorage.setItem('onboarding:v1', 'not-json')
    const { acknowledgeLesson, teaching, vaultState } = useOnboardingState()
    expect(vaultState('v1')).toEqual({})
    acknowledgeLesson('v1', 'orientation.resources')
    expect(teaching('v1').lessons).toEqual({ 'orientation.resources': 'acknowledged' })
  })

  it('shares one session ledger across consumers when storage is unavailable', () => {
    const descriptor = Object.getOwnPropertyDescriptor(window, 'localStorage')
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      get() {
        throw new Error('storage unavailable')
      },
    })
    try {
      const first = useOnboardingState()
      const second = useOnboardingState()
      first.acknowledgeLesson('v1', 'orientation.resources')
      expect(second.teaching('v1').lessons['orientation.resources']).toBe('acknowledged')
    } finally {
      if (descriptor) Object.defineProperty(window, 'localStorage', descriptor)
    }
  })
})
