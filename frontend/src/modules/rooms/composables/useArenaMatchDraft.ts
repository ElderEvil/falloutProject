import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useDwellerMedicalStore } from '@/modules/dwellers/stores/dwellerMedical'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useArenaStore } from '../stores/arena'
import type { ArenaCreature, ArenaMode, ArenaRosterEntry } from '../api/arena'
import type { ArenaRoomController } from './useArenaRoom'
import {
  arenaSlotsFor,
  creatureKeyOf,
  creatureViewToFighter,
  type ArenaCreatureView,
  type ArenaSlotFighter,
  type ArenaSlotKey,
  type ArenaTeamSide,
} from '../models/arena'
import { notifyErrorOnce } from '@/core/utils/errorHandler'

export type ArenaStage = 'fighters' | 'fight'

export interface ArenaModeOption {
  value: ArenaMode
  label: string
  description: string
  tier: number
}

export const ARENA_MODE_OPTIONS: ArenaModeOption[] = [
  { value: 'duel', label: 'Duel', description: 'Two dwellers, one on each side.', tier: 1 },
  {
    value: 'brawl',
    label: 'Team fight',
    description: 'Two dwellers against two dwellers.',
    tier: 2,
  },
  {
    value: 'training',
    label: 'Bot training',
    description: 'Two dwellers against two training bots.',
    tier: 2,
  },
  {
    value: 'hunt',
    label: 'Creature hunt',
    description: 'Two dwellers against two creatures.',
    tier: 3,
  },
]

const HUNT_PRESETS = [
  { name: 'Pest Control', keys: ['radroach-swarm', 'bloatfly'] },
  { name: 'Wasteland Pack', keys: ['mole-rat-pack', 'night-stalker'] },
  { name: 'Heavyweights', keys: ['mirelurk', 'yao-guai'] },
]

type DraftSlots = Record<ArenaSlotKey, string | null>

const EMPTY_DRAFT: DraftSlots = { a: null, b: null, c: null, d: null }

const TEAM_SIDES = ['A', 'B'] as const

export function useArenaMatchDraft(
  vaultId: string,
  roomId: string,
  controller: ArenaRoomController
) {
  const authStore = useAuthStore()
  const { management: dwellerManagementStore } = useDwellerStore()
  const medicalStore = useDwellerMedicalStore()
  const vaultStore = useVaultStore()
  const arenaStore = useArenaStore()

  const stage = ref<ArenaStage>('fighters')
  const stageTouched = ref(false)
  const mode = ref<ArenaMode>('duel')
  const draft = ref<DraftSlots>({ ...EMPTY_DRAFT })
  const opponentKeys = ref<string[]>([])
  const botKeys = ref<Record<ArenaTeamSide, string | null>>({ A: null, B: null })
  const botEnabled = ref<Record<ArenaTeamSide, boolean>>({ A: false, B: false })
  const openPicker = ref<ArenaSlotKey | null>(null)
  const creaturePickerOpen = ref(false)
  const creaturePickerIndex = ref<number | null>(null)
  const draftDirty = ref(false)
  const isStarting = ref(false)
  const isStopping = ref(false)
  const isHealing = ref(false)

  const roomState = computed(() => controller.roomState.value)
  const teamFighters = computed(() => [
    ...(roomState.value?.team_a ?? []),
    ...(roomState.value?.team_b ?? []),
  ])
  const isFighting = computed(
    () => !!roomState.value?.fight_started && !(roomState.value?.match_done ?? false)
  )
  const isDone = computed(() => roomState.value?.match_done ?? false)
  const canChangeFighters = computed(() => !isFighting.value && !isStarting.value)
  const canStart = computed(() => {
    if (!modeUnlocked(mode.value) || isFighting.value) return false
    if (activeSlots.value.some((slot) => !draft.value[slot] || !slotFighter(slot)?.health))
      return false
    return !isCatalogMode.value || opponentKeys.value.filter(Boolean).length === 2
  })
  const availableModes = computed<ArenaMode[]>(() => roomState.value?.available_modes ?? [])
  const countdown = computed(() => roomState.value?.countdown_remaining ?? 0)
  const nextAttackTeam = computed(() => roomState.value?.next_attack_team ?? 'A')

  const roster = computed(() => roomState.value?.roster ?? [])
  const candidates = computed(() =>
    [...(roomState.value?.candidates?.length ? roomState.value.candidates : roster.value)].sort(
      (a, b) =>
        Number(b.room_id === roomId || roster.value.some((entry) => entry.id === b.id)) -
        Number(a.room_id === roomId || roster.value.some((entry) => entry.id === a.id))
    )
  )
  const isCatalogMode = computed(() => mode.value === 'hunt' || mode.value === 'training')

  const partnerSlot = (side: ArenaTeamSide): ArenaSlotKey => (side === 'A' ? 'c' : 'd')
  const slotsFor = (side: ArenaTeamSide) => arenaSlotsFor(mode.value, side)
  const activeSlots = computed<ArenaSlotKey[]>(() => [...slotsFor('A'), ...slotsFor('B')])

  const needsLabel = computed(() => {
    const missing = activeSlots.value.filter((slot) => !draft.value[slot]).length
    const opponents = isCatalogMode.value ? 2 - opponentKeys.value.filter(Boolean).length : 0
    return (
      [
        missing ? `Choose ${missing} more dweller${missing === 1 ? '' : 's'}` : '',
        opponents
          ? `Choose ${opponents} more ${mode.value === 'training' ? 'bot' : 'creature'}${opponents === 1 ? '' : 's'}`
          : '',
      ]
        .filter(Boolean)
        .join(' · ') || 'Ready to fight'
    )
  })

  const winnerName = computed(() => roomState.value?.winner_name ?? null)
  const matchReward = computed(() => {
    const events = [...(roomState.value?.events ?? [])].reverse()
    const finish = events.find((event) => event.kind === 'finish')
    return finish
      ? events.find((event) => event.kind === 'reward' && event.round_seq === finish.round_seq)
          ?.message
      : undefined
  })

  const statusLabel = computed(() => {
    if (isFighting.value) return 'FIGHT IN PROGRESS'
    if (isDone.value) return 'DONE'
    if (canStart.value) return 'READY'
    return needsLabel.value
  })

  const modeUnlocked = (value: ArenaMode) => availableModes.value.includes(value)

  const creaturesByKey = computed(
    () => new Map(arenaStore.creatures.map((creature) => [creature.key, creature]))
  )
  const huntPresets = computed(() =>
    HUNT_PRESETS.filter((preset) => preset.keys.every((key) => creaturesByKey.value.has(key)))
  )
  const selectedHuntPreset = computed(
    () =>
      huntPresets.value.find(
        (preset) =>
          preset.keys.length === opponentKeys.value.length &&
          preset.keys.every((key) => opponentKeys.value.includes(key))
      )?.name ?? ''
  )
  // Team B in hunt: local picks first so a pending draft stays visible, overlaid
  // with the server's live HP once a creature is confirmed.
  const creatureSlots = computed<Array<ArenaCreatureView | null>>(() => {
    const live = new Map(
      (roomState.value?.team_b ?? [])
        .filter((fighter) => fighter.is_creature || fighter.is_robot)
        .map((fighter) => [creatureKeyOf(fighter.id), fighter])
    )
    const slots = Array.from({ length: 2 }, (_, index): ArenaCreatureView | null => {
      const key = opponentKeys.value[index]
      const stateFighter = live.get(key)
      if (stateFighter) {
        return {
          key,
          is_robot: stateFighter.is_robot,
          name: stateFighter.name,
          power: stateFighter.power,
          health: stateFighter.health,
          max_health: stateFighter.max_health,
          id: stateFighter.id,
        }
      }
      const catalogue = creaturesByKey.value.get(key)
      if (!catalogue) return null
      return {
        key,
        is_robot: catalogue.is_robot,
        name: catalogue.name,
        power: catalogue.power,
        health: catalogue.max_hp,
        max_health: catalogue.max_hp,
        id: null,
      }
    })
    while (slots.length < 2) slots.push(null)
    return slots
  })

  const creaturePickerOptions = computed(() =>
    arenaStore.creatures.filter(
      (creature) =>
        !!creature.is_robot === (mode.value === 'training') &&
        !opponentKeys.value.includes(creature.key)
    )
  )

  const botView = (side: ArenaTeamSide): ArenaCreatureView | null => {
    const key = botKeys.value[side]
    if (!key) return null
    const live = (side === 'A' ? roomState.value?.team_a : roomState.value?.team_b)?.find(
      (fighter) => fighter.is_robot && creatureKeyOf(fighter.id) === key
    )
    const entry = creaturesByKey.value.get(key)
    if (!entry) return null
    return {
      key,
      is_robot: true,
      name: entry.name,
      power: live?.power ?? entry.power,
      health: live?.health ?? entry.max_hp,
      max_health: live?.max_health ?? entry.max_hp,
      id: live?.id ?? null,
    }
  }

  const serverFightersById = computed(() => {
    const byId = new Map<string, ArenaSlotFighter>()
    for (const fighter of teamFighters.value) byId.set(fighter.id, fighter)
    return byId
  })

  // A slot shows the server's fighter once confirmed; a pick the server has not
  // accepted yet falls back to its roster entry (no combat power exposed there).
  const slotFighter = (slot: ArenaSlotKey): ArenaSlotFighter | null => {
    const id = draft.value[slot]
    if (!id) return null
    const serverFighter = serverFightersById.value.get(id)
    if (serverFighter) {
      const candidate = candidates.value.find((entry) => entry.id === id)
      return !isFighting.value && candidate
        ? { ...serverFighter, health: candidate.health, max_health: candidate.max_health }
        : serverFighter
    }
    const entry = candidates.value.find((candidate) => candidate.id === id)
    if (!entry) return null
    return {
      id: entry.id,
      name: entry.name,
      level: entry.level,
      health: entry.health,
      max_health: entry.max_health,
      power: null,
      active_skill: entry.active_skill ?? null,
      is_creature: false,
      is_robot: false,
      image_url: entry.image_url,
      thumbnail_url: entry.thumbnail_url,
      age_group: entry.age_group,
      race: entry.race,
    }
  }

  // Every dweller appears exactly once: on the stage (slots) or on the bench.
  const selectedIds = computed(
    () => new Set(Object.values(draft.value).filter((id): id is string => !!id))
  )
  const bench = computed(() => roster.value.filter((entry) => !selectedIds.value.has(entry.id)))

  const pickerOptions = (slot: ArenaSlotKey) => {
    const takenElsewhere = new Set(
      activeSlots.value
        .filter((key) => key !== slot)
        .map((key) => draft.value[key])
        .filter((id): id is string => !!id)
    )
    return candidates.value.filter((entry) => !takenElsewhere.has(entry.id))
  }

  const previewTeamFor = (side: ArenaTeamSide): Array<ArenaSlotFighter | null> => {
    if (side === 'B' && isCatalogMode.value) {
      return creatureSlots.value.map((view) => (view ? creatureViewToFighter(view) : null))
    }
    return slotsFor(side).map((slot) => {
      if (side === 'B' && slot === partnerSlot('B') && botEnabled.value.B) {
        const bot = botView('B')
        return bot ? creatureViewToFighter(bot) : null
      }
      return slotFighter(slot)
    })
  }
  const teamA = computed(() => previewTeamFor('A'))
  const teamB = computed(() => previewTeamFor('B'))
  const slotKeysA = computed(() => slotsFor('A'))
  const slotKeysB = computed(() => (isCatalogMode.value ? [] : slotsFor('B')))

  const closePickers = () => {
    openPicker.value = null
    creaturePickerOpen.value = false
    creaturePickerIndex.value = null
  }

  const setStage = (next: ArenaStage) => {
    stage.value = next
    stageTouched.value = true
    closePickers()
  }

  const syncFromState = () => {
    const state = roomState.value
    if (!state || draftDirty.value) return
    const teamA = state.team_a ?? []
    const teamB = state.team_b ?? []
    for (const side of TEAM_SIDES) {
      const team = side === 'A' ? teamA : teamB
      const bot =
        state.mode !== 'brawl' || side === 'A'
          ? undefined
          : team.find((fighter) => fighter.is_robot)
      botKeys.value[side] = bot ? creatureKeyOf(bot.id) : null
      botEnabled.value[side] = !!bot
    }
    if (state.mode === 'hunt' || state.mode === 'training') {
      mode.value = state.mode
      draft.value = {
        a: teamA[0]?.id ?? state.fighter_a_id,
        c: botKeys.value.A ? null : (teamA[1]?.id ?? null),
        b: null,
        d: null,
      }
      opponentKeys.value = teamB
        .filter((fighter) => fighter.is_creature || fighter.is_robot)
        .map((fighter) => creatureKeyOf(fighter.id))
    } else if (state.mode === 'brawl') {
      mode.value = 'brawl'
      draft.value = {
        a: teamA[0]?.id ?? state.fighter_a_id,
        c: botKeys.value.A ? null : (teamA[1]?.id ?? null),
        b: teamB[0]?.id ?? state.fighter_b_id,
        d: botKeys.value.B ? null : (teamB[1]?.id ?? null),
      }
    } else {
      mode.value = 'duel'
      draft.value = { ...EMPTY_DRAFT, a: state.fighter_a_id, b: state.fighter_b_id }
    }
    if (!stageTouched.value) {
      stage.value = state.fight_started || state.match_done ? 'fight' : 'fighters'
      stageTouched.value = true
    }
  }

  watch(roomState, syncFromState, { immediate: true })
  watch(isFighting, (fighting) => {
    if (fighting) setStage('fight')
  })
  watch(isDone, (done) => {
    if (done) setStage('fight')
  })

  const loadCreatures = async () => {
    if (!authStore.token) return
    await arenaStore.fetchCreatures(vaultId, authStore.token)
  }

  onMounted(() => {
    void loadCreatures()
  })

  const switchMode = (next: ArenaMode) => {
    if (next === mode.value || !canChangeFighters.value || !modeUnlocked(next)) return
    const previous = mode.value
    mode.value = next
    if (previous === 'hunt' || previous === 'training' || next === 'hunt' || next === 'training')
      opponentKeys.value = []
    if (next === 'duel') {
      botKeys.value = { A: null, B: null }
      botEnabled.value = { A: false, B: false }
    }
    if (next === 'hunt' || next === 'training') {
      botKeys.value.B = null
      botEnabled.value.B = false
    }
    openPicker.value = null
    creaturePickerOpen.value = false
    creaturePickerIndex.value = null
    if (next === 'duel') {
      draft.value.c = null
      draft.value.d = null
    }
    if (next === 'hunt' || next === 'training') {
      draft.value.b = null
      draft.value.d = null
    }
    draftDirty.value = true
  }

  const selectMode = (next: ArenaMode) => {
    if (isFighting.value || !modeUnlocked(next)) return
    if (next !== mode.value) switchMode(next)
    setStage('fighters')
  }

  const togglePicker = (slot: ArenaSlotKey) => {
    if (isFighting.value) return
    creaturePickerOpen.value = false
    creaturePickerIndex.value = null
    openPicker.value = openPicker.value === slot ? null : slot
  }

  const selectFighter = (slot: ArenaSlotKey, entry: ArenaRosterEntry) => {
    draft.value[slot] = entry.id
    openPicker.value = null
    if (slot === 'c' || slot === 'd') {
      const side = slot === 'c' ? 'A' : 'B'
      botKeys.value[side] = null
      botEnabled.value[side] = false
    }

    draftDirty.value = true
  }

  const clearFighter = (slot: ArenaSlotKey) => {
    draft.value[slot] = null
    draftDirty.value = true
  }

  const toggleCreaturePicker = (index?: number) => {
    if (isFighting.value) return
    openPicker.value = null
    const target = index ?? opponentKeys.value.length
    if (creaturePickerOpen.value && creaturePickerIndex.value === target) {
      creaturePickerOpen.value = false
      creaturePickerIndex.value = null
      return
    }
    creaturePickerOpen.value = true
    creaturePickerIndex.value = target
  }

  const selectCreature = (creature: ArenaCreature) => {
    if (isFighting.value) return
    const index = creaturePickerIndex.value
    if (index !== null && index < 2) {
      const next = [...opponentKeys.value]
      if (next.some((key, position) => position !== index && key === creature.key)) return
      next[index] = creature.key
      opponentKeys.value = next
    } else {
      if (opponentKeys.value.length >= 2 || opponentKeys.value.includes(creature.key)) return
      opponentKeys.value = [...opponentKeys.value, creature.key]
    }
    creaturePickerOpen.value = false
    creaturePickerIndex.value = null
    draftDirty.value = true
  }

  const selectHuntPreset = (value: unknown) => {
    if (mode.value !== 'hunt' || !canChangeFighters.value) return
    const preset = huntPresets.value.find((candidate) => candidate.name === value)
    if (!preset) return
    opponentKeys.value = [...preset.keys]
    creaturePickerOpen.value = false
    creaturePickerIndex.value = null
    draftDirty.value = true
  }

  const clearCreature = (key: string) => {
    opponentKeys.value = opponentKeys.value.map((candidate) => (candidate === key ? '' : candidate))
    creaturePickerOpen.value = false
    creaturePickerIndex.value = null
    draftDirty.value = true
  }

  const clearBot = (side: ArenaTeamSide) => {
    botKeys.value[side] = null
    draftDirty.value = true
  }

  const injuredFighters = computed(() =>
    teamFighters.value.filter(
      (fighter) =>
        !fighter.is_creature && fighter.max_health > 0 && fighter.health / fighter.max_health < 0.5
    )
  )

  const healInjured = async () => {
    if (!authStore.token || isHealing.value) return
    isHealing.value = true
    try {
      for (const fighter of injuredFighters.value) {
        const healed = await medicalStore.useStimpack(fighter.id, authStore.token)
        if (!healed) break
      }
      await Promise.all([controller.refresh(), vaultStore.refreshVault(vaultId, authStore.token)])
    } finally {
      isHealing.value = false
    }
  }

  const clearJournal = async () => {
    if (!authStore.token) return
    await arenaStore.clearEvents(vaultId, roomId, authStore.token)
  }

  const unassign = async (entry: ArenaRosterEntry) => {
    if (!authStore.token) return
    try {
      await dwellerManagementStore.unassignDwellerFromRoom(entry.id, authStore.token)
    } catch (error) {
      notifyErrorOnce(error, 'Failed to remove dweller from the Arena')
    }
  }

  const startFight = async (): Promise<boolean> => {
    if (!authStore.token || !canStart.value || isStarting.value) return false
    isStarting.value = true
    try {
      const ok = await controller.startFight({
        mode: mode.value,
        fighterAId: draft.value.a,
        fighterBId: isCatalogMode.value ? null : draft.value.b,
        fighterCId: mode.value === 'duel' ? null : draft.value.c,
        fighterDId: isCatalogMode.value || mode.value === 'duel' ? null : draft.value.d,
        opponentKeys: isCatalogMode.value ? opponentKeys.value.filter(Boolean) : [],
      })
      if (ok) {
        draftDirty.value = false
        syncFromState()
        setStage('fight')
      }
      return ok
    } finally {
      isStarting.value = false
    }
  }

  const stopFight = async (): Promise<boolean> => {
    if (!authStore.token || isStopping.value) return false
    isStopping.value = true
    try {
      const ok = await controller.stopFight()
      if (ok) setStage('fighters')
      return ok
    } finally {
      isStopping.value = false
    }
  }

  const rematch = async (): Promise<boolean> => {
    if (!authStore.token || isStarting.value) return false
    return startFight()
  }

  return reactive({
    roomState,
    stage,
    mode,
    modeOptions: ARENA_MODE_OPTIONS,
    draft,
    opponentKeys,
    botKeys,
    botEnabled,
    openPicker,
    creaturePickerOpen,
    creaturePickerIndex,
    roster,
    candidates,
    teamA,
    teamB,
    slotKeysA,
    slotKeysB,
    teamFighters,
    bench,
    injuredFighters,
    isFighting,
    isDone,
    canChangeFighters,
    canStart,
    availableModes,
    countdown,
    nextAttackTeam,
    needsLabel,
    statusLabel,
    winnerName,
    matchReward,
    isStarting,
    isStopping,
    isHealing,
    huntPresets,
    selectedHuntPreset,
    creatureSlots,
    creaturePickerOptions,
    modeUnlocked,
    setStage,
    selectMode,
    switchMode,
    slotFighter,
    pickerOptions,
    togglePicker,
    selectFighter,
    clearFighter,
    toggleCreaturePicker,
    selectCreature,
    clearCreature,
    selectHuntPreset,
    clearBot,
    botView,
    startFight,
    stopFight,
    rematch,
    healInjured,
    clearJournal,
    unassign,
    closePickers,
  })
}

export type ArenaMatchDraft = ReturnType<typeof useArenaMatchDraft>
