import { computed, onMounted, onScopeDispose, ref, watch } from 'vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useSound } from '@/core/composables/useSound'
import { usePolling } from '@/core/composables/usePolling'
import { useCombatPlayback } from '@/modules/combat/composables/useCombatPlayback'
import { useArenaStore } from '../stores/arena'
import type { ArenaFighter } from '../api/arena'

export function useArenaRoom(vaultId: string, roomId: string) {
  const authStore = useAuthStore()
  const arenaStore = useArenaStore()
  const { playSound } = useSound()
  const isLoading = ref(true)
  const loadFailed = ref(false)
  const pendingSkills = ref(new Set<string>())
  const authoritativeState = computed(() => arenaStore.getRoom(roomId))
  const teamFighters = computed(() => [
    ...(authoritativeState.value?.team_a ?? []),
    ...(authoritativeState.value?.team_b ?? []),
  ])
  const playback = useCombatPlayback(
    () => {
      const state = authoritativeState.value
      return state
        ? {
            key: [
              vaultId,
              roomId,
              state.mode,
              ...teamFighters.value.map((fighter) => fighter.id),
            ].join(':'),
            health: Object.fromEntries(
              teamFighters.value.map((fighter) => [fighter.id, fighter.health])
            ),
            events: state.events ?? [],
          }
        : null
    },
    (event) => playSound(event.action.skill ? 'arenaSkill' : 'incidentHit')
  )

  const roomState = computed(() => {
    const state = authoritativeState.value
    if (!state) return null
    const displayed = (fighters: ArenaFighter[]) =>
      fighters.map((fighter) => ({
        ...fighter,
        health: playback.health.value[fighter.id] ?? fighter.health,
      }))
    return {
      ...state,
      team_a: displayed(state.team_a),
      team_b: displayed(state.team_b),
      fighters: displayed(state.fighters ?? teamFighters.value),
      match_done: state.match_done && !playback.isPlaying.value,
      fight_started: state.fight_started || playback.isPlaying.value,
      can_start: state.can_start && !playback.isPlaying.value,
    }
  })
  const attackingFighterId = computed(() => playback.active.value?.action.actor_id ?? null)
  const attackingTeam = computed<'A' | 'B' | null>(() => {
    const id = attackingFighterId.value
    if (authoritativeState.value?.team_a.some((fighter) => fighter.id === id)) return 'A'
    if (authoritativeState.value?.team_b.some((fighter) => fighter.id === id)) return 'B'
    return null
  })
  const skillBurst = computed(() => {
    const event = playback.active.value
    return event?.action.skill
      ? { id: event.id, message: event.action.skill, icon: event.action.skill_icon }
      : null
  })

  const seenEvents = new Set<string>()
  const previousCharge = new Map<string, number>()
  let feedbackPrimed = false
  let lastCountdown = 0
  let lastStarted = false
  let loadSequence = 0
  let finishPending = false
  let disposed = false
  onScopeDispose(() => {
    disposed = true
  })

  watch(playback.isPlaying, (playing) => {
    if (!playing && finishPending) {
      finishPending = false
      playSound('arenaFinish')
    }
  })

  const recordFeedback = () => {
    const state = authoritativeState.value
    if (!state) return
    const events = state.events ?? []
    const fresh = events.filter((event) => !seenEvents.has(event.id))
    seenEvents.clear()
    for (const event of events) seenEvents.add(event.id)
    const ready = teamFighters.value
      .map((fighter) => {
        const charge = fighter.active_skill?.charge ?? 0
        const before = previousCharge.get(fighter.id)
        previousCharge.set(fighter.id, charge)
        return before !== undefined && before < 100 && charge >= 100 && fighter.health > 0
      })
      .some(Boolean)
    if (feedbackPrimed) {
      if (fresh.some((event) => event.kind === 'finish')) {
        if (playback.isPlaying.value) finishPending = true
        else playSound('arenaFinish')
      } else if (ready && !state.match_done) playSound('arenaReady')
      else if (state.countdown_remaining > 0 && state.countdown_remaining !== lastCountdown)
        playSound('arenaCountdown')
      else if (
        state.fight_started &&
        !state.match_done &&
        state.countdown_remaining === 0 &&
        (!lastStarted || lastCountdown > 0)
      )
        playSound('arenaStart')
    }
    lastCountdown = state.countdown_remaining
    lastStarted = state.fight_started
    feedbackPrimed = true
  }

  const load = async (silent = false) => {
    if (!authStore.token) return
    const sequence = ++loadSequence
    const token = authStore.token
    const loaded = await arenaStore.fetchState(vaultId, token, silent)
    if (disposed || sequence !== loadSequence || token !== authStore.token) return
    loadFailed.value = !loaded
    recordFeedback()
    isLoading.value = false
  }

  const queueSkill = async (fighterId: string) => {
    const state = authoritativeState.value
    if (
      !authStore.token ||
      pendingSkills.value.has(fighterId) ||
      state?.match_done ||
      !teamFighters.value.some((fighter) => fighter.id === fighterId && fighter.health > 0)
    )
      return
    pendingSkills.value.add(fighterId)
    try {
      await arenaStore.queueSkill(vaultId, roomId, fighterId, authStore.token)
      if (!disposed) recordFeedback()
    } finally {
      pendingSkills.value.delete(fighterId)
    }
  }

  const resetDamageTracking = () => {
    finishPending = false
    playback.reset()
  }
  const startFight = async (): Promise<boolean> => {
    if (!authStore.token) return false
    const ok = await arenaStore.startFight(vaultId, roomId, authStore.token)
    if (ok && !disposed) {
      resetDamageTracking()
      recordFeedback()
    }
    return ok
  }
  const stopFight = async (): Promise<boolean> => {
    if (!authStore.token) return false
    const ok = await arenaStore.stopFight(vaultId, roomId, authStore.token)
    if (ok && !disposed) {
      resetDamageTracking()
      recordFeedback()
    }
    return ok
  }

  onMounted(() => {
    void load()
  })
  usePolling(() => load(true), { interval: 1_000, immediate: false })

  return {
    roomState,
    isLoading,
    loadFailed,
    pendingSkills,
    damageNumbers: playback.damageNumbers,
    activeAction: playback.active,
    combatPhase: playback.phase,
    attackingTeam,
    attackingFighterId,
    skillBurst,
    load,
    retry: () => load(false),
    refresh: () => load(true),
    queueSkill,
    startFight,
    stopFight,
    resetDamageTracking,
  }
}

export type ArenaRoomController = ReturnType<typeof useArenaRoom>
