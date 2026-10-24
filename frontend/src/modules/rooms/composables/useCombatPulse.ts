import { nextTick, onScopeDispose, ref, watch, type Ref } from 'vue'

/**
 * True for one animation window after `source` changes. Clearing the flag for a
 * frame lets the same CSS animation restart when the next round lands.
 */
export function useCombatPulse(source: Ref<string | number | null | undefined>, durationMs = 450) {
  const active = ref(false)
  let timer: ReturnType<typeof setTimeout> | null = null

  watch(source, async (value) => {
    if (value === null || value === undefined) return
    active.value = false
    await nextTick()
    active.value = true
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      active.value = false
    }, durationMs)
  })

  onScopeDispose(() => {
    if (timer) clearTimeout(timer)
  })

  return active
}
