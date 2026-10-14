import { useStorage } from '@vueuse/core'

export interface OnboardingState {
  skipped?: boolean
  welcomed?: boolean
  created?: boolean
}

const STORAGE_KEY = 'onboarding:v1'

/**
 * Per-vault tour state. Objective progress itself stays server-side; this only tracks
 * whether the player welcomed or skipped the guide for each vault, and exposes the
 * reset a settings control needs to re-arm it.
 */
export function useOnboardingState() {
  const state = useStorage<Record<string, OnboardingState>>(STORAGE_KEY, {})

  const vaultState = (vaultId: string | null | undefined): OnboardingState =>
    vaultId ? (state.value[vaultId] ?? {}) : {}

  const patch = (vaultId: string | null | undefined, next: Partial<OnboardingState>): void => {
    if (!vaultId) return
    state.value = { ...state.value, [vaultId]: { ...state.value[vaultId], ...next } }
  }

  const reset = (vaultId: string | null | undefined): void => {
    if (!vaultId || !(vaultId in state.value)) return
    const next = { ...state.value }
    delete next[vaultId]
    state.value = next
  }

  const resetAll = (): void => {
    state.value = {}
  }

  return { state, vaultState, patch, reset, resetAll }
}
