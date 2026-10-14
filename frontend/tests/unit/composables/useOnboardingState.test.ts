import { beforeEach, describe, expect, it } from 'vitest'
import { useOnboardingState } from '@/core/composables/useOnboardingState'

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
    expect(JSON.parse(localStorage.getItem('onboarding:v1') ?? '{}')).toEqual({})
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
})
