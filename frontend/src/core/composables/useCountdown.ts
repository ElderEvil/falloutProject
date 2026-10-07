import {
  getCurrentScope,
  onScopeDispose,
  ref,
  toValue,
  watch,
  type MaybeRefOrGetter,
  type Ref,
} from 'vue'
import { useIntervalFn } from '@vueuse/core'

/**
 * Seconds-based countdown seeded from a reactive source.
 *
 * Seeds `secondsLeft` from the current source value, re-seeds whenever the
 * source changes, decrements once per `intervalMs`, and stops at zero. Mirrors
 * the hand-rolled countdowns in the map marker modal: the interval only runs
 * while there is time left, `isFinished` flips when it reaches zero, and the
 * timer is disposed with the owning effect scope.
 */
export function useCountdown(
  source: MaybeRefOrGetter<number>,
  intervalMs = 1000
): { secondsLeft: Ref<number>; isFinished: Ref<boolean> } {
  const secondsLeft = ref(0)
  const isFinished = ref(true)

  const { pause, resume } = useIntervalFn(
    () => {
      const next = Math.max(0, secondsLeft.value - 1)
      secondsLeft.value = next
      if (next === 0) {
        isFinished.value = true
        pause()
      }
    },
    intervalMs,
    { immediate: false }
  )

  watch(
    () => toValue(source),
    (seconds) => {
      pause()
      const seeded = Math.max(0, seconds)
      secondsLeft.value = seeded
      isFinished.value = seeded === 0
      if (seeded > 0) resume()
    },
    { immediate: true }
  )

  if (getCurrentScope()) onScopeDispose(pause)

  return { secondsLeft, isFinished }
}
