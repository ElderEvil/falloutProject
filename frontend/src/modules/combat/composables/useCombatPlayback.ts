import { computed, onScopeDispose, ref, watch } from 'vue'
import { useDocumentVisibility } from '@vueuse/core'
import type { CombatPlaybackSnapshot, PlayingCombatAction } from '../models/playback'

const duration = (event: PlayingCombatAction) => (event.action.skill ? 550 : 350)

/** Plays resolved facts locally; never advances combat or writes server state. */
export function useCombatPlayback(
  source: () => CombatPlaybackSnapshot | null,
  onImpact?: (event: PlayingCombatAction) => void
) {
  const health = ref<Record<string, number>>({})
  const active = ref<PlayingCombatAction | null>(null)
  const phase = ref<'prepare' | 'impact' | null>(null)
  const damageNumbers = ref<Array<{ id: number; fighterId: string; amount: number }>>([])
  const visibility = useDocumentVisibility()
  const queue: PlayingCombatAction[] = []
  const timers = new Set<ReturnType<typeof setTimeout>>()
  const unconfirmedHealth = new Map<string, { before: Set<number>; after: number }>()
  let latest: CombatPlaybackSnapshot | null = null
  let lastEventId: string | undefined
  let lastUpdate = 0
  let rate = 1
  let sequence = 0
  let primed = false

  const later = (callback: () => void, ms: number) => {
    const timer = setTimeout(() => {
      timers.delete(timer)
      callback()
    }, ms)
    timers.add(timer)
  }

  const reset = () => {
    for (const timer of timers) clearTimeout(timer)
    timers.clear()
    unconfirmedHealth.clear()
    queue.length = 0
    active.value = null
    phase.value = null
    damageNumbers.value = []
    primed = false
    lastEventId = undefined
  }

  const synchronize = () => {
    reset()
    health.value = { ...latest?.health }
    lastEventId = latest?.events.at(-1)?.id
    primed = latest !== null
  }

  const reconcileHealth = () => {
    const current = { ...latest?.health }
    for (const [id, pending] of unconfirmedHealth) {
      // Incident rosters and journals refresh independently. Preserve an impact
      // while the roster still reports one of its earlier HP values.
      if (current[id] === undefined || pending.before.has(current[id])) current[id] = pending.after
      else unconfirmedHealth.delete(id)
    }
    health.value = current
  }

  const playNext = () => {
    const event = queue.shift()
    active.value = event ? { ...event, accelerated: rate > 1 } : null
    if (!event) {
      phase.value = null
      reconcileHealth()
      return
    }
    phase.value = 'prepare'
    for (const target of event.action.targets) {
      if (target.health_before != null) health.value[target.target_id] = target.health_before
    }
    const actionDuration = duration(event) / rate
    const windup = (event.action.skill ? 250 : 150) / rate
    later(() => {
      phase.value = 'impact'
      for (const target of event.action.targets) {
        if (target.health_after != null) {
          const pending = unconfirmedHealth.get(target.target_id) ?? {
            before: new Set<number>(),
            after: target.health_after,
          }
          if (target.health_before != null) pending.before.add(target.health_before)
          pending.after = target.health_after
          unconfirmedHealth.set(target.target_id, pending)
          health.value[target.target_id] = target.health_after
        }
        if (target.damage > 0) {
          const id = ++sequence
          damageNumbers.value.push({ id, fighterId: target.target_id, amount: target.damage })
          later(() => {
            damageNumbers.value = damageNumbers.value.filter((number) => number.id !== id)
          }, 900)
        }
      }
      onImpact?.(event)
      later(playNext, actionDuration - windup)
    }, windup)
  }

  watch(
    source,
    (snapshot) => {
      const previousKey = latest?.key
      latest = snapshot
      const now = Date.now()
      const missedHistory =
        lastEventId && !snapshot?.events.some((event) => event.id === lastEventId)
      if (
        !primed ||
        !snapshot ||
        previousKey !== snapshot.key ||
        missedHistory ||
        visibility.value === 'hidden' ||
        now - lastUpdate > 10_000
      ) {
        synchronize()
      } else {
        const index = snapshot.events.findIndex((event) => event.id === lastEventId)
        const fresh = snapshot.events
          .slice(index + 1)
          .filter((event): event is PlayingCombatAction => !!event.action)
        lastEventId = snapshot.events.at(-1)?.id
        queue.push(...fresh)
        const backlog = queue.reduce((ms, event) => ms + duration(event), 0)
        rate = Math.max(1, Math.min(3, backlog / 1800))
        if (backlog / rate > 6000) synchronize()
        else if (!active.value) playNext()
      }
      lastUpdate = now
    },
    { immediate: true, flush: 'sync' }
  )

  // Hidden tabs cannot keep animation timers in step with the live fight.
  watch(visibility, synchronize)
  onScopeDispose(reset)

  return {
    health,
    active,
    phase,
    damageNumbers,
    isPlaying: computed(() => active.value !== null),
    reset: synchronize,
  }
}
