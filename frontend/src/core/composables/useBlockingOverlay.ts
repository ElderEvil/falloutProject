import { computed, onScopeDispose, ref, watch, type WatchSource } from 'vue'

/**
 * Registry of overlays that own the player's attention: dialogs, confirmation
 * overlays and full-screen popups. Consumers (the onboarding guide) read
 * `isOverlayBlocking` instead of sniffing the DOM for `[role="dialog"]`.
 */
const openBlockers = ref<ReadonlyMap<symbol, string | undefined>>(new Map())

/** True while any registered blocking overlay is open. */
export const isOverlayBlocking = computed(() => openBlockers.value.size > 0)

/** A lesson may guide a named overlay only while no other overlay owns attention. */
export function isOnlyBlockingOverlay(scope: string): boolean {
  return openBlockers.value.size === 1 && [...openBlockers.value.values()][0] === scope
}

/**
 * Register a blocking overlay for as long as `open` is true. Released
 * automatically when the calling component unmounts.
 */
export function useBlockingOverlay(open: WatchSource<boolean>, onboardingScope?: string): void {
  const key = Symbol('blocking-overlay')
  const sync = (value: boolean) => {
    const next = new Map(openBlockers.value)
    if (value) next.set(key, onboardingScope)
    else next.delete(key)
    openBlockers.value = next
  }
  // Sync flush: a dialog that just opened must suspend the guide in the same
  // tick, with no window where both are on screen.
  watch(open, sync, { immediate: true, flush: 'sync' })
  onScopeDispose(() => sync(false))
}
