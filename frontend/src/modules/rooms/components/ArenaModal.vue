<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { Alert, AlertDescription, AlertTitle } from '@/core/components/ui/alert'
import { Button } from '@/core/components/ui/button'
import { Badge } from '@/core/components/ui/badge'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/core/components/ui/card'
import { ToggleGroup, ToggleGroupItem } from '@/core/components/ui/toggle-group'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/core/components/ui/tabs'
import { Progress } from '@/core/components/ui/progress'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/core/components/ui/tooltip'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useToast } from '@/core/composables/useToast'
import { usePolling } from '@/core/composables/usePolling'
import ArenaFighterSlot from './ArenaFighterSlot.vue'
import ArenaCreatureSlot from './ArenaCreatureSlot.vue'
import BattleLog from './BattleLog.vue'
import ComponentLoader from '@/core/components/common/ComponentLoader.vue'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import { useArenaStore } from '../stores/arena'
import { useDwellerMedicalStore } from '@/modules/dwellers/stores/dwellerMedical'
import type { ArenaCreature, ArenaFighter, ArenaMode, ArenaRosterEntry } from '../api/arena'
import {
  arenaSlotsFor,
  creatureKeyOf,
  type ArenaCreatureView,
  type ArenaSlotFighter,
  type ArenaSlotKey,
  type ArenaTeamSide,
} from '../models/arena'
import { battleLogKindLabel, type BattleLogEntry } from '../models/battleLog'

interface Props {
  vaultId: string
  roomId: string
}

const props = defineProps<Props>()

const MODE_OPTIONS: Array<{ value: ArenaMode; label: string }> = [
  { value: 'duel', label: 'Duel' },
  { value: 'brawl', label: 'Brawl' },
  { value: 'hunt', label: 'Hunt' },
]

type DraftSlots = Record<ArenaSlotKey, string | null>

const EMPTY_DRAFT: DraftSlots = { a: null, b: null, c: null, d: null }

const authStore = useAuthStore()
const toast = useToast()
const { management: dwellerManagementStore } = useDwellerStore()
const medicalStore = useDwellerMedicalStore()
const arenaStore = useArenaStore()

const isLoading = ref(true)
const loadFailed = ref(false)
const damageNumbers = ref<Array<{ id: number; fighterId: string; amount: number }>>([])
const previousHp = ref<Record<string, number>>({})
const openPicker = ref<ArenaSlotKey | null>(null)
const creaturePickerOpen = ref(false)
const mode = ref<ArenaMode>('duel')
const draft = ref<DraftSlots>({ ...EMPTY_DRAFT })
const opponentKeys = ref<string[]>([])
const TEAM_SIDES = ['A', 'B'] as const
const botKeys = ref<Record<ArenaTeamSide, string | null>>({ A: null, B: null })
const botEnabled = ref<Record<ArenaTeamSide, boolean>>({ A: false, B: false })
const botPicker = ref<ArenaTeamSide | null>(null)
const partnerSlot = (side: ArenaTeamSide): ArenaSlotKey => (side === 'A' ? 'c' : 'd')
const draftDirty = ref(false)
const isStarting = ref(false)
let damageSeq = 0
let loadSequence = 0
const pendingDamageTimers = new Set<ReturnType<typeof setTimeout>>()

onUnmounted(() => {
  for (const timer of pendingDamageTimers) clearTimeout(timer)
  pendingDamageTimers.clear()
})

const roomState = computed(() => arenaStore.getRoom(props.roomId))

const winnerName = computed(() => roomState.value?.winner_name ?? null)

const teamFighters = computed<ArenaFighter[]>(() => [
  ...(roomState.value?.team_a ?? []),
  ...(roomState.value?.team_b ?? []),
])

const damageForId = (fighterId: string | null) =>
  fighterId ? damageNumbers.value.filter((entry) => entry.fighterId === fighterId) : []

const recordDamage = (fighter: ArenaFighter) => {
  const prev = previousHp.value[fighter.id]
  if (prev !== undefined && fighter.health < prev) {
    const entry = { id: ++damageSeq, fighterId: fighter.id, amount: prev - fighter.health }
    damageNumbers.value.push(entry)
    const timer = setTimeout(() => {
      pendingDamageTimers.delete(timer)
      damageNumbers.value = damageNumbers.value.filter((d) => d.id !== entry.id)
    }, 900)
    pendingDamageTimers.add(timer)
  }
  previousHp.value[fighter.id] = fighter.health
}

const applyState = () => {
  for (const fighter of teamFighters.value) recordDamage(fighter)
  const liveIds = new Set(teamFighters.value.map((f) => f.id))
  for (const id of Object.keys(previousHp.value)) {
    if (!liveIds.has(id)) delete previousHp.value[id]
  }
}

// The server only reveals teams for a fully selected match; without this the
// half-built draft of a brawl would be wiped by the 1 s state poll.
const syncFromState = () => {
  const state = roomState.value
  if (!state || draftDirty.value) return
  for (const side of TEAM_SIDES) {
    const team = side === 'A' ? state.team_a : state.team_b
    const bot =
      state.mode === 'duel' || (state.mode === 'hunt' && side === 'B')
        ? undefined
        : team.find((fighter) => fighter.is_robot)
    botKeys.value[side] = bot ? creatureKeyOf(bot.id) : null
    botEnabled.value[side] = !!bot
  }
  if (state.mode === 'hunt') {
    mode.value = 'hunt'
    draft.value = {
      a: state.team_a[0]?.id ?? state.fighter_a_id,
      c: botKeys.value.A ? null : (state.team_a[1]?.id ?? null),
      b: null,
      d: null,
    }
    opponentKeys.value = state.team_b
      .filter((fighter) => fighter.is_creature)
      .map((fighter) => creatureKeyOf(fighter.id))
  } else if (state.mode === 'brawl') {
    mode.value = 'brawl'
    draft.value = {
      a: state.team_a[0]?.id ?? state.fighter_a_id,
      c: botKeys.value.A ? null : (state.team_a[1]?.id ?? null),
      b: state.team_b[0]?.id ?? state.fighter_b_id,
      d: botKeys.value.B ? null : (state.team_b[1]?.id ?? null),
    }
  } else {
    mode.value = 'duel'
    draft.value = { ...EMPTY_DRAFT, a: state.fighter_a_id, b: state.fighter_b_id }
  }
}

const load = async (silent = false) => {
  if (!authStore.token) return
  const sequence = ++loadSequence
  const loaded = await arenaStore.fetchState(props.vaultId, authStore.token, silent)
  if (sequence !== loadSequence) return
  loadFailed.value = !loaded
  applyState()
  syncFromState()
  isLoading.value = false
}

const loadCreatures = async () => {
  if (!authStore.token) return
  await arenaStore.fetchCreatures(props.vaultId, authStore.token)
}

onMounted(() => {
  void load()
  void loadCreatures()
})

usePolling(() => load(true), { interval: 1_000, immediate: false })

const roster = computed(() => roomState.value?.roster ?? [])
const isDone = computed(() => roomState.value?.match_done ?? false)
const canStart = computed(() => (roomState.value?.can_start ?? false) && !draftDirty.value)
const isFighting = computed(() => (roomState.value?.fight_started ?? false) && !isDone.value)
const canChangeFighters = computed(() => !isFighting.value)
const availableModes = computed(() => roomState.value?.available_modes ?? [])
const countdown = computed(() => roomState.value?.countdown_remaining ?? 0)

const slotsFor = (side: ArenaTeamSide) => arenaSlotsFor(mode.value, side)
const activeSlots = computed<ArenaSlotKey[]>(() => [...slotsFor('A'), ...slotsFor('B')])
const needsLabel = computed(() =>
  mode.value === 'hunt'
    ? 'NEEDS DWELLERS + CREATURES'
    : mode.value === 'brawl'
      ? 'NEEDS 2 DWELLERS + PARTNERS'
      : 'NEEDS 2 FIGHTERS'
)

const creaturesByKey = computed(
  () => new Map(arenaStore.creatures.map((creature) => [creature.key, creature]))
)

// Team B in hunt: local picks first so a pending draft stays visible, overlaid
// with the server's live HP once a creature is confirmed.
const creatureSlots = computed<Array<ArenaCreatureView | null>>(() => {
  const live = new Map(
    (roomState.value?.team_b ?? [])
      .filter((fighter) => fighter.is_creature)
      .map((fighter) => [creatureKeyOf(fighter.id), fighter])
  )
  const slots = opponentKeys.value.map((key): ArenaCreatureView | null => {
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
  if (slots.length < 2) slots.push(null)
  return slots
})

const creaturePickerOptions = computed(() =>
  arenaStore.creatures.filter((creature) => !opponentKeys.value.includes(creature.key))
)

const robotOptions = computed(() => arenaStore.creatures.filter((creature) => creature.is_robot))
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
const choosePartnerType = (side: ArenaTeamSide, bot: boolean) => {
  if (!canChangeFighters.value || botEnabled.value[side] === bot) return
  botEnabled.value[side] = bot
  botKeys.value[side] = null
  draft.value[partnerSlot(side)] = null
  botPicker.value = bot ? side : null
  openPicker.value = null
  creaturePickerOpen.value = false
  draftDirty.value = true
  void commitDraft()
}
const selectBot = (side: ArenaTeamSide, bot: ArenaCreature) => {
  botKeys.value[side] = bot.key
  botPicker.value = null
  draftDirty.value = true
  void commitDraft()
}
const clearBot = (side: ArenaTeamSide) => {
  botKeys.value[side] = null
  draftDirty.value = true
  void commitDraft()
}

const serverFightersById = computed(() => {
  const byId = new Map<string, ArenaFighter>()
  for (const fighter of teamFighters.value) byId.set(fighter.id, fighter)
  return byId
})

// A slot shows the server's fighter once confirmed; a pick the server has not
// accepted yet falls back to its roster entry (no combat power exposed there).
const slotFighter = (slot: ArenaSlotKey): ArenaSlotFighter | null => {
  const id = draft.value[slot]
  if (!id) return null
  const serverFighter = serverFightersById.value.get(id)
  if (serverFighter) return serverFighter
  const entry = roster.value.find((candidate) => candidate.id === id)
  if (!entry) return null
  return {
    id: entry.id,
    name: entry.name,
    level: entry.level,
    health: entry.health,
    max_health: entry.max_health,
    power: null,
    is_creature: false,
    is_robot: false,
    image_url: entry.image_url,
    thumbnail_url: entry.thumbnail_url,
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
  return roster.value.filter((entry) => !takenElsewhere.has(entry.id))
}

const togglePicker = (slot: ArenaSlotKey) => {
  if (isFighting.value) return
  creaturePickerOpen.value = false
  openPicker.value = openPicker.value === slot ? null : slot
}

// Brawl needs all four slots before the server accepts the selection; hunt needs
// a lead dweller and at least one creature; duel accepts any pair (including
// empty), so it persists on every change as before. Clearing the last slot of a
// brawl/hunt draft therefore stays a pending local edit: the backend rejects an
// incomplete selection, so the server keeps the previous one while `draftDirty`
// holds `canStart` false and blocks the poll from overwriting the edit until it
// is valid again.
const commitDraft = async () => {
  if (!authStore.token) return
  if (
    mode.value !== 'duel' &&
    TEAM_SIDES.some((side) => botEnabled.value[side] && !botKeys.value[side])
  )
    return
  if (
    mode.value === 'brawl' &&
    TEAM_SIDES.some(
      (side) =>
        !draft.value[side === 'A' ? 'a' : 'b'] ||
        !(draft.value[partnerSlot(side)] || botKeys.value[side])
    )
  )
    return
  if (mode.value === 'hunt' && (!draft.value.a || opponentKeys.value.length === 0)) return
  const ok = await arenaStore.setFighters(
    props.vaultId,
    props.roomId,
    {
      mode: mode.value,
      fighterAId: draft.value.a,
      fighterBId: mode.value === 'hunt' ? null : draft.value.b,
      fighterCId: botKeys.value.A ? null : draft.value.c,
      teamABotKey: mode.value === 'duel' ? null : botKeys.value.A,
      teamBBotKey: mode.value === 'brawl' ? botKeys.value.B : null,
      fighterDId: mode.value === 'hunt' ? null : draft.value.d,
      ...(mode.value === 'hunt' ? { opponentKeys: [...opponentKeys.value] } : {}),
    },
    authStore.token
  )
  if (!ok) {
    draftDirty.value = false
    syncFromState()
    return
  }
  draftDirty.value = false
  openPicker.value = null
  creaturePickerOpen.value = false
  previousHp.value = {}
}

const switchMode = (next: ArenaMode) => {
  if (next === mode.value || !canChangeFighters.value || !availableModes.value.includes(next))
    return
  mode.value = next
  botPicker.value = null
  if (next === 'duel') {
    botKeys.value = { A: null, B: null }
    botEnabled.value = { A: false, B: false }
  }
  if (next === 'hunt') {
    botKeys.value.B = null
    botEnabled.value.B = false
  }
  openPicker.value = null
  creaturePickerOpen.value = false
  if (next === 'duel') {
    draft.value.c = null
    draft.value.d = null
  }
  if (next === 'hunt') {
    draft.value.b = null
    draft.value.d = null
  }
  draftDirty.value = true
  void commitDraft()
}

const selectFighter = (slot: ArenaSlotKey, entry: ArenaRosterEntry) => {
  draft.value[slot] = entry.id
  openPicker.value = null
  if (slot === 'c' || slot === 'd') {
    const side = slot === 'c' ? 'A' : 'B'
    botKeys.value[side] = null
    botEnabled.value[side] = false
  }

  // Smart pairing: when exactly one slot is empty and exactly one candidate
  // remains, fill it — picking all but one almost always means the last
  // dweller belongs in the last corner.
  const emptySlots = activeSlots.value.filter(
    (key) =>
      !draft.value[key] &&
      !(key === 'c' && botEnabled.value.A) &&
      !(key === 'd' && botEnabled.value.B)
  )
  const taken = new Set(Object.values(draft.value).filter((id): id is string => !!id))
  const remaining = roster.value.filter((candidate) => !taken.has(candidate.id))
  if (emptySlots.length === 1 && remaining.length === 1)
    draft.value[emptySlots[0]] = remaining[0].id

  draftDirty.value = true
  void commitDraft()
}

const clearFighter = (slot: ArenaSlotKey) => {
  draft.value[slot] = null
  draftDirty.value = true
  void commitDraft()
}

const toggleCreaturePicker = () => {
  if (isFighting.value) return
  openPicker.value = null
  creaturePickerOpen.value = !creaturePickerOpen.value
}

const selectCreature = (creature: ArenaCreature) => {
  if (opponentKeys.value.length >= 2 || opponentKeys.value.includes(creature.key)) return
  opponentKeys.value = [...opponentKeys.value, creature.key]
  creaturePickerOpen.value = false
  draftDirty.value = true
  void commitDraft()
}

const clearCreature = (key: string) => {
  opponentKeys.value = opponentKeys.value.filter((candidate) => candidate !== key)
  draftDirty.value = true
  void commitDraft()
}

const unassign = async (entry: ArenaRosterEntry) => {
  if (!authStore.token) return
  try {
    await dwellerManagementStore.unassignDwellerFromRoom(entry.id, authStore.token)
  } catch {
    toast.error('Failed to remove dweller from the Arena')
  }
}

// Post-battle conveniences: patch up the losers, clear the room for the next
// match. Fighters under 50% HP are the ones a stimpack actually helps.
const injuredFighters = computed(() =>
  teamFighters.value.filter(
    (fighter) =>
      !fighter.is_creature && fighter.max_health > 0 && fighter.health / fighter.max_health < 0.5
  )
)

const isHealing = ref(false)
const healInjured = async () => {
  if (!authStore.token || isHealing.value) return
  isHealing.value = true
  try {
    for (const fighter of injuredFighters.value) {
      await medicalStore.useStimpack(fighter.id, authStore.token)
    }
    previousHp.value = {}
    await load(true)
  } finally {
    isHealing.value = false
  }
}

const clearJournal = async () => {
  if (!authStore.token) return
  await arenaStore.clearEvents(props.vaultId, props.roomId, authStore.token)
}

const startFight = async () => {
  if (!authStore.token || !canStart.value || isStarting.value) return
  isStarting.value = true
  try {
    const ok = await arenaStore.startFight(props.vaultId, props.roomId, authStore.token)
    if (ok) previousHp.value = {}
  } finally {
    isStarting.value = false
  }
}

const JOURNAL_KIND_LABELS: Record<string, string> = {
  hit: 'HIT',
  finish: 'FINISH',
  reward: 'REWARD',
}

// Round sequence is the journal's reading order — normalize it here so the
// list cannot flip if the wire order changes.
const journalEntries = computed<BattleLogEntry[]>(() =>
  [...(roomState.value?.events ?? [])]
    .sort((a, b) => a.round_seq - b.round_seq)
    .map((event) => ({
      id: event.id,
      kind: battleLogKindLabel(event.kind, JOURNAL_KIND_LABELS),
      message: event.message,
      meta: `R${event.round_seq}`,
    }))
)

const hpPercent = (entry: ArenaRosterEntry) =>
  entry.max_health > 0 ? Math.round((entry.health / entry.max_health) * 100) : 0

const hpTone = (entry: ArenaRosterEntry) => {
  const pct = hpPercent(entry)
  return pct < 25 ? 'danger' : pct < 50 ? 'warning' : 'success'
}

const modeDescription = computed(() => {
  if (mode.value === 'hunt')
    return '1–2 dwellers against creatures. A training bot can join your lead dweller.'
  if (mode.value === 'brawl')
    return 'Two teams: a lead dweller and a second dweller or training bot.'
  return 'Two assigned dwellers, one on each side.'
})

const statusLabel = computed(() => {
  if (isFighting.value) return 'FIGHT IN PROGRESS'
  if (isDone.value) return 'DONE'
  if (canStart.value) return 'READY'
  return roster.value.length ? needsLabel.value : 'ASSIGN DWELLERS'
})

const updateMode = (value: unknown) => {
  const option = MODE_OPTIONS.find((option) => option.value === value)
  if (option) switchMode(option.value)
}
</script>

<template>
  <div class="arena-panel flex flex-col gap-3">
    <ComponentLoader v-if="isLoading" label="Loading arena…" />

    <Alert v-else-if="loadFailed" variant="destructive">
      <AlertTitle>Arena unavailable</AlertTitle>
      <AlertDescription>Unable to load Arena status.</AlertDescription>
      <Button class="mt-3" variant="secondary" size="sm" @click="load()">RETRY</Button>
    </Alert>

    <template v-else>
      <Tabs as-child :model-value="mode" activation-mode="manual" @update:model-value="updateMode">
        <Card size="sm" class="overflow-visible border border-theme-primary/30">
          <CardHeader>
            <CardTitle class="sr-only">Match</CardTitle>
            <div class="flex flex-wrap items-center justify-between gap-2">
              <!-- @vue-ignore -->
              <TabsList variant="line" aria-label="Match mode">
                <!-- @vue-ignore -->
                <TabsTrigger
                  v-for="(option, index) in MODE_OPTIONS"
                  :key="option.value"
                  :value="option.value"
                  class="px-3 py-1.5"
                  :disabled="!canChangeFighters || !availableModes.includes(option.value)"
                  :title="
                    availableModes.includes(option.value)
                      ? undefined
                      : `Unlocks at Tier ${index + 1}`
                  "
                >
                  {{ option.label }}
                  <Icon v-if="!availableModes.includes(option.value)" icon="mdi:lock-outline" />
                </TabsTrigger>
              </TabsList>
              <Badge :variant="canStart ? 'default' : 'outline'">{{ statusLabel }}</Badge>
            </div>
            <CardDescription class="text-xs">{{ modeDescription }}</CardDescription>
            <p v-if="mode !== 'duel'" class="text-xs text-muted-foreground">
              Bots reset each match and earn no rewards.
            </p>
          </CardHeader>
          <TabsContent :value="mode" as-child>
            <CardContent class="arena-content flex flex-col gap-3">
              <Alert v-if="!roster.length">
                <Icon icon="mdi:account-plus-outline" :ariaHidden="true" />
                <AlertTitle>Build your arena roster</AlertTitle>
                <AlertDescription>
                  Assign adult dwellers to the Arena first using an empty dweller slot in the room
                  preview.
                </AlertDescription>
              </Alert>
              <template v-else>
                <Alert v-if="mode !== 'hunt' && roster.length < 2">
                  <AlertTitle>One more adult needed</AlertTitle>
                  <AlertDescription
                    >Assign another adult to the Arena so each side has a dweller.</AlertDescription
                  >
                </Alert>
                <div
                  class="teams-row grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-start gap-2 sm:gap-4"
                >
                  <template v-for="side in TEAM_SIDES" :key="side">
                    <div
                      v-if="side === 'B'"
                      class="versus flex flex-col items-center gap-1 self-center"
                    >
                      <Transition name="countdown-pop" mode="out-in">
                        <span
                          v-if="isFighting && countdown > 0"
                          :key="countdown"
                          class="countdown-number text-3xl font-bold text-danger"
                          >{{ countdown }}</span
                        >
                        <Icon
                          v-else
                          icon="mdi:sword-cross"
                          class="size-5 text-theme-primary"
                          :ariaHidden="true"
                        />
                      </Transition>
                      <span v-if="countdown === 0" class="text-xs font-bold text-theme-primary"
                        >VS</span
                      >
                    </div>
                    <div class="team flex min-w-0 flex-col gap-3">
                      <span
                        v-if="mode !== 'duel'"
                        class="team-label text-center text-xs font-semibold tracking-wider text-muted-foreground"
                        >{{ side === 'B' && mode === 'hunt' ? 'CREATURES' : `TEAM ${side}` }}</span
                      >
                      <template v-if="side === 'B' && mode === 'hunt'">
                        <ArenaCreatureSlot
                          v-for="(slot, index) in creatureSlots"
                          :key="slot?.key ?? 'creature-slot-' + index"
                          :creature="slot"
                          :can-change="canChangeFighters"
                          :damage-numbers="damageForId(slot?.id ?? null)"
                          :options="creaturePickerOptions"
                          :mirror-bots="true"
                          :picker-open="creaturePickerOpen && slot === null"
                          @toggle-picker="toggleCreaturePicker"
                          @clear="clearCreature"
                          @select="selectCreature"
                        />
                      </template>
                      <template v-else>
                        <div v-for="slot in slotsFor(side)" :key="slot" class="min-w-0">
                          <!-- @vue-ignore -->
                          <ToggleGroup
                            v-if="slot === partnerSlot(side)"
                            type="single"
                            variant="outline"
                            size="sm"
                            class="mb-2"
                            :model-value="botEnabled[side] ? 'bot' : 'dweller'"
                            :disabled="!canChangeFighters"
                            :aria-label="`Team ${side} partner`"
                            @update:model-value="
                              (value) => {
                                if (value === 'bot' || value === 'dweller')
                                  choosePartnerType(side, value === 'bot')
                              }
                            "
                          >
                            <!-- @vue-ignore -->
                            <ToggleGroupItem value="dweller">Dweller</ToggleGroupItem>
                            <!-- @vue-ignore -->
                            <ToggleGroupItem value="bot">Bot</ToggleGroupItem>
                          </ToggleGroup>
                          <ArenaCreatureSlot
                            v-if="slot === partnerSlot(side) && botEnabled[side]"
                            :creature="botView(side)"
                            :can-change="canChangeFighters"
                            :damage-numbers="damageForId(botView(side)?.id ?? null)"
                            :options="robotOptions"
                            :mirror="side === 'B'"
                            :friendly="side === 'A'"
                            empty-label="+ ADD BOT"
                            :picker-open="botPicker === side"
                            @toggle-picker="botPicker = botPicker === side ? null : side"
                            @clear="clearBot(side)"
                            @select="selectBot(side, $event)"
                          />
                          <ArenaFighterSlot
                            v-else
                            :side="slot"
                            :fighter="slotFighter(slot)"
                            :can-change="canChangeFighters"
                            :damage-numbers="damageForId(draft[slot])"
                            :options="pickerOptions(slot)"
                            :picker-open="openPicker === slot"
                            @toggle-picker="togglePicker"
                            @clear="clearFighter"
                            @select="selectFighter"
                          />
                        </div>
                      </template>
                    </div>
                  </template>
                </div>
              </template>

              <Alert v-if="winnerName" class="result-banner">
                <Icon icon="mdi:trophy" :ariaHidden="true" />
                <AlertTitle v-if="roomState?.mode === 'duel'"
                  >MATCH COMPLETE &mdash; {{ winnerName }} wins!</AlertTitle
                >
                <AlertTitle v-else>MATCH COMPLETE &mdash; Victory for {{ winnerName }}!</AlertTitle>
              </Alert>
              <div v-if="isDone && injuredFighters.length" class="flex justify-center">
                <Button variant="secondary" size="sm" :disabled="isHealing" @click="healInjured">
                  <!-- @vue-ignore -->
                  <Icon
                    v-if="isHealing"
                    icon="mdi:loading"
                    data-icon="inline-start"
                    class="animate-spin"
                  />
                  <!-- @vue-ignore -->
                  <Icon v-else icon="mdi:medication" data-icon="inline-start" />
                  HEAL INJURED ({{ injuredFighters.length }})
                </Button>
              </div>
              <div v-if="canStart" class="flex justify-center">
                <Button :disabled="isStarting" @click="startFight">
                  <!-- @vue-ignore -->
                  <Icon
                    v-if="isStarting"
                    icon="mdi:loading"
                    data-icon="inline-start"
                    class="animate-spin"
                  />
                  <!-- @vue-ignore -->
                  <Icon v-else icon="mdi:sword-cross" data-icon="inline-start" />
                  START FIGHT
                </Button>
              </div>
            </CardContent>
          </TabsContent>
        </Card>
      </Tabs>

      <section v-if="bench.length" aria-label="Arena bench">
        <Card size="sm">
          <CardHeader>
            <div class="flex items-center justify-between gap-2">
              <CardTitle class="flex items-center gap-2">
                <Icon
                  icon="mdi:account-group-outline"
                  class="size-4 text-theme-primary"
                  :ariaHidden="true"
                />
                Bench
              </CardTitle>
              <Badge variant="secondary">{{ bench.length }} waiting</Badge>
            </div>
          </CardHeader>
          <CardContent class="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            <Card v-for="entry in bench" :key="entry.id" size="sm" class="gap-2 py-3">
              <CardHeader>
                <div class="flex items-start gap-2">
                  <DwellerPortrait
                    :image-url="entry.image_url"
                    :thumbnail-url="entry.thumbnail_url"
                    :alt="entry.name"
                    prefer-thumbnail
                    image-class="size-10 shrink-0 rounded-md object-cover"
                    fallback-class="size-10 shrink-0 text-theme-primary"
                  />
                  <div class="flex min-w-0 flex-1 flex-col gap-1">
                    <CardTitle class="break-words">{{ entry.name }}</CardTitle>
                    <CardDescription>Level {{ entry.level }}</CardDescription>
                  </div>
                  <TooltipProvider v-if="!isFighting" :delay-duration="200">
                    <Tooltip>
                      <TooltipTrigger as-child>
                        <Button
                          size="icon-sm"
                          variant="ghost"
                          :aria-label="`Remove ${entry.name} from Arena`"
                          @click="unassign(entry)"
                        >
                          <Icon icon="mdi:account-minus-outline" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>Remove {{ entry.name }} from Arena</TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
              </CardHeader>
              <CardContent class="flex flex-col gap-2">
                <span class="text-xs text-muted-foreground tabular-nums"
                  >{{ entry.health }} / {{ entry.max_health }} HP</span
                >
                <Progress
                  :model-value="hpPercent(entry)"
                  :tone="hpTone(entry)"
                  :label="`${entry.name} health`"
                  :value-text="`${entry.health} of ${entry.max_health} HP`"
                />
              </CardContent>
            </Card>
          </CardContent>
        </Card>
      </section>

      <Card size="sm">
        <CardHeader>
          <div class="flex items-center justify-between gap-2">
            <CardTitle class="flex items-center gap-2">
              <Icon
                icon="mdi:clipboard-text-clock-outline"
                class="size-4 text-theme-primary"
                :ariaHidden="true"
              />
              Battle Journal
            </CardTitle>
            <Button v-if="roomState?.events.length" variant="ghost" size="xs" @click="clearJournal"
              >CLEAR</Button
            >
          </div>
        </CardHeader>
        <CardContent>
          <BattleLog :entries="journalEntries" empty-text="No rounds fought yet." />
        </CardContent>
      </Card>

      <details class="text-xs text-muted-foreground">
        <summary
          class="cursor-pointer rounded-sm py-1 focus-visible:outline focus-visible:outline-ring"
        >
          Match rewards &amp; recovery
        </summary>
        <p class="pt-2 leading-relaxed">
          Winners gain happiness and XP. Losing dwellers lose happiness and are left at 1 HP. Check
          their health before the next fight. Change the fighters to start a new match.
        </p>
      </details>
    </template>
  </div>
</template>

<style scoped>
.countdown-pop-enter-active,
.countdown-pop-leave-active {
  transition:
    opacity 0.3s ease,
    transform 0.3s ease;
}
.countdown-pop-enter-from {
  opacity: 0;
  transform: scale(1.6);
}
.countdown-pop-leave-to {
  opacity: 0;
  transform: scale(0.6);
}
@media (prefers-reduced-motion: reduce) {
  .countdown-pop-enter-active,
  .countdown-pop-leave-active {
    transition: none;
  }
}
</style>
