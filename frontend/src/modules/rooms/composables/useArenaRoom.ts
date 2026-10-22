import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useSound } from '@/core/composables/useSound'
import { usePolling } from '@/core/composables/usePolling'
import { useArenaStore } from '../stores/arena'
import type { ArenaFighter } from '../api/arena'

export function useArenaRoom(vaultId: string, roomId: string) {
  const authStore = useAuthStore()
  const arenaStore = useArenaStore()
  const { playSound } = useSound()

  const isLoading = ref(true)
  const loadFailed = ref(false)
  const pendingSkills = ref(new Set<string>())
  const damageNumbers = ref<Array<{ id: number; fighterId: string; amount: number }>>([])
  const attackingTeam = ref<'A' | 'B' | null>(null)
  const skillBurst = ref<{ id: string; message: string } | null>(null)
  const previousHp = ref<Record<string, number>>({})

  const seenEvents = new Set<string>()
  const previousCharge = new Map<string, number>()
  const pendingDamageTimers = new Set<ReturnType<typeof setTimeout>>()
  let feedbackPrimed = false
  let lastCountdown = 0
  let lastStarted = false
  let damageSeq = 0
  let loadSequence = 0
  let burstTimer: ReturnType<typeof setTimeout> | undefined
  let attackTimer: ReturnType<typeof setTimeout> | undefined

  const roomState = computed(() => arenaStore.getRoom(roomId))
  const teamFighters = computed<ArenaFighter[]>(() => [
    ...(roomState.value?.team_a ?? []),
    ...(roomState.value?.team_b ?? []),
  ])

  const recordDamage = (fighter: ArenaFighter) => {
    const prev = previousHp.value[fighter.id]
    if (prev !== undefined && fighter.health < prev) {
      const entry = { id: ++damageSeq, fighterId: fighter.id, amount: prev - fighter.health }
      damageNumbers.value.push(entry)
      const timer = setTimeout(() => {
        pendingDamageTimers.delete(timer)
        damageNumbers.value = damageNumbers.value.filter((item) => item.id !== entry.id)
      }, 900)
      pendingDamageTimers.add(timer)
    }
    previousHp.value[fighter.id] = fighter.health
  }

  const recordFeedback = () => {
    const state = roomState.value
    if (!state) return
    const fresh = state.events.filter((event) => !seenEvents.has(event.id))
    for (const event of state.events) seenEvents.add(event.id)
    const newlyReady = teamFighters.value.map((fighter) => {
      const charge = fighter.active_skill?.charge ?? 0
      const before = previousCharge.get(fighter.id)
      previousCharge.set(fighter.id, charge)
      return before !== undefined && before < 100 && charge >= 100 && fighter.health > 0
    })
    const ready = newlyReady.some(Boolean)
    if (feedbackPrimed) {
      if (fresh.some((event) => event.kind === 'turn')) {
        attackingTeam.value = state.next_attack_team === 'B' ? 'A' : 'B'
        clearTimeout(attackTimer)
        attackTimer = setTimeout(() => {
          attackingTeam.value = null
        }, 550)
      }
      const skill = [...fresh].reverse().find((event) => event.kind === 'skill')
      if (fresh.some((event) => event.kind === 'finish')) playSound('arenaFinish')
      else if (skill) playSound('arenaSkill')
      else if (ready && !state.match_done) playSound('arenaReady')
      else if (state.countdown_remaining > 0 && state.countdown_remaining !== lastCountdown)
        playSound('arenaCountdown')
      else if (
        state.fight_started &&
        !state.match_done &&
        state.countdown_remaining === 0 &&
        (!lastStarted || lastCountdown > 0)
      )
        playSound('arenaStart')
      else if (fresh.some((event) => event.kind === 'hit')) playSound('incidentHit')
      if (skill) {
        skillBurst.value = { id: skill.id, message: skill.message }
        clearTimeout(burstTimer)
        burstTimer = setTimeout(() => {
          skillBurst.value = null
        }, 1600)
      }
    }
    lastCountdown = state.countdown_remaining
    lastStarted = state.fight_started
    feedbackPrimed = true
  }

  const applyState = () => {
    recordFeedback()
    for (const fighter of teamFighters.value) recordDamage(fighter)
    const liveIds = new Set(teamFighters.value.map((fighter) => fighter.id))
    for (const id of Object.keys(previousHp.value)) {
      if (!liveIds.has(id)) delete previousHp.value[id]
    }
  }

  const load = async (silent = false) => {
    if (!authStore.token) return
    const sequence = ++loadSequence
    const loaded = await arenaStore.fetchState(vaultId, authStore.token, silent)
    if (sequence !== loadSequence) return
    loadFailed.value = !loaded
    applyState()
    isLoading.value = false
  }

  const queueSkill = async (fighterId: string) => {
    if (!authStore.token || pendingSkills.value.has(fighterId)) return
    pendingSkills.value.add(fighterId)
    try {
      await arenaStore.queueSkill(vaultId, roomId, fighterId, authStore.token)
      applyState()
    } finally {
      pendingSkills.value.delete(fighterId)
    }
  }

  const startFight = async (): Promise<boolean> => {
    if (!authStore.token) return false
    const ok = await arenaStore.startFight(vaultId, roomId, authStore.token)
    if (ok) {
      previousHp.value = {}
      applyState()
    }
    return ok
  }

  const resetDamageTracking = () => {
    previousHp.value = {}
    damageNumbers.value = []
  }

  onMounted(() => {
    void load()
  })

  usePolling(() => load(true), { interval: 1_000, immediate: false })

  onUnmounted(() => {
    for (const timer of pendingDamageTimers) clearTimeout(timer)
    pendingDamageTimers.clear()
    clearTimeout(burstTimer)
    clearTimeout(attackTimer)
  })

  return {
    roomState,
    isLoading,
    loadFailed,
    pendingSkills,
    damageNumbers,
    attackingTeam,
    skillBurst,
    load,
    retry: () => load(false),
    refresh: () => load(true),
    queueSkill,
    startFight,
    resetDamageTracking,
  }
}

export type ArenaRoomController = ReturnType<typeof useArenaRoom>
