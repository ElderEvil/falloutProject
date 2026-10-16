import { computed, onScopeDispose, ref, watch, type WatchSource } from 'vue'

/**
 * Registry of overlays that own the player's attention: dialogs, confirmation
 * overlays and full-screen popups. Consumers (the onboarding guide) read
 * `isOverlayBlocking` instead of sniffing the DOM for `[role="dialog"]`.
 */
const openBlockers = ref<ReadonlySet<symbol>>(new Set())

/** True while any registered blocking overlay is open. */
export const isOverlayBlocking = computed(() => openBlockers.value.size > 0)

/**
 * Register a blocking overlay for as long as `open` is true. Released
 * automatically when the calling component unmounts.
 */
export function useBlockingOverlay(open: WatchSource<boolean>): void {
  const key = Symbol('blocking-overlay')
  const sync = (value: boolean) => {
    const next = new Set(openBlockers.value)
    if (value) next.add(key)
    else next.delete(key)
    openBlockers.value = next
  }
  // Sync flush: a dialog that just opened must suspend the guide in the same
  // tick, with no window where both are on screen.
  watch(open, sync, { immediate: true, flush: 'sync' })
  onScopeDispose(() => sync(false))
}
