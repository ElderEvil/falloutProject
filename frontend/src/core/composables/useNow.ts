import { computed, type Ref } from 'vue'
import { useIntervalFn, useNow as vueUseNow } from '@vueuse/core'

/**
 * Reactive current time as epoch milliseconds, re-read every `intervalMs`.
 *
 * Thin wrapper over VueUse's `useNow`: the clock is driven by `useIntervalFn`
 * (house style, see `map.ts`) so the tick rate is configurable, and the interval
 * is disposed with the current Vue effect scope when one exists.
 */
export function useNow(intervalMs = 1000): Readonly<Ref<number>> {
  const date = vueUseNow({
    scheduler: (tick) => useIntervalFn(tick, intervalMs, { immediate: true }),
  })

  return computed(() => date.value.getTime())
}
