<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { Alert, AlertTitle } from '@/core/components/ui/alert'
import { Button } from '@/core/components/ui/button'
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
  arenaTeamSize,
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
  { value: 'duel', label: 'DUEL' },
  { value: 'brawl', label: 'BRAWL' },
  { value: 'hunt', label: 'HUNT' },
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
  if (state.mode === 'hunt') {
    mode.value = 'hunt'
    draft.value = {
      a: state.team_a[0]?.id ?? state.fighter_a_id,
      c: state.team_a[1]?.id ?? null,
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
      c: state.team_a[1]?.id ?? null,
      b: state.team_b[0]?.id ?? state.fighter_b_id,
      d: state.team_b[1]?.id ?? null,
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
    : `NEEDS ${arenaTeamSize(mode.value) * 2} FIGHTERS`
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
  if (mode.value === 'brawl' && activeSlots.value.some((slot) => !draft.value[slot])) return
  if (mode.value === 'hunt' && (!draft.value.a || opponentKeys.value.length === 0)) return
  const ok = await arenaStore.setFighters(
    props.vaultId,
    props.roomId,
    {
      mode: mode.value,
      fighterAId: draft.value.a,
      fighterBId: mode.value === 'hunt' ? null : draft.value.b,
      fighterCId: draft.value.c,
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

  // Smart pairing: when exactly one slot is empty and exactly one candidate
  // remains, fill it — picking all but one almost always means the last
  // dweller belongs in the last corner.
  const emptySlots = activeSlots.value.filter((key) => !draft.value[key])
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
    (fighter) => fighter.max_health > 0 && fighter.health / fighter.max_health < 0.5
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

const hpClass = (entry: ArenaRosterEntry) => {
  const pct = hpPercent(entry)
  if (pct < 25) return 'hp-critical'
  if (pct < 50) return 'hp-low'
  return 'hp-healthy'
}

const HP_FILL_COLOR: Record<string, string> = {
  'hp-healthy': 'var(--color-success)',
  'hp-low': 'var(--color-warning)',
  'hp-critical': 'var(--color-danger)',
}

const hpFillColor = (entry: ArenaRosterEntry) =>
  HP_FILL_COLOR[hpClass(entry)] ?? HP_FILL_COLOR['hp-healthy']!
</script>

<template>
  <div class="arena-panel">
    <div class="arena-header">
      <Icon icon="mdi:sword-cross" class="arena-header-icon" />
      <div>
        <h2 class="arena-title">ARENA</h2>
        <p class="arena-subtitle">
          {{ roomState?.room_name ?? 'Arena' }} &middot; Tier {{ roomState?.tier ?? 1 }}
        </p>
      </div>
      <span class="arena-badge" :class="{ ready: canStart, done: isDone }">
        {{ isDone ? 'DONE' : canStart ? 'READY' : needsLabel }}
      </span>
    </div>

    <ComponentLoader v-if="isLoading" label="Loading arena…" />

    <Alert v-else-if="loadFailed" variant="default" class="border-danger bg-danger/10 text-danger">
      <AlertTitle>Arena unavailable</AlertTitle>
      <p>Unable to load Arena status.</p>
      <Button class="mt-3" variant="secondary" size="sm" @click="load()">RETRY</Button>
    </Alert>

    <div v-else class="arena-content">
      <!-- Fighters -->
      <div class="section">
        <div class="section-header">
          <h3 class="section-title">
            <Icon icon="mdi:sword-cross" class="section-title-icon" />
            Fighters
          </h3>
          <div class="mode-select" role="group" aria-label="Match mode">
            <Button
              v-for="option in MODE_OPTIONS"
              :key="option.value"
              :variant="mode === option.value ? 'default' : 'secondary'"
              size="sm"
              :disabled="!canChangeFighters || !availableModes.includes(option.value)"
              :title="
                availableModes.includes(option.value)
                  ? undefined
                  : 'Upgrade the Arena to unlock this mode'
              "
              :aria-pressed="mode === option.value"
              @click="switchMode(option.value)"
            >
              {{ option.label }}
            </Button>
          </div>
        </div>
        <p
          v-if="roomState && availableModes.length < MODE_OPTIONS.length"
          class="mb-3 text-xs text-gray-400"
        >
          Tier 2 unlocks Brawl. Tier 3 unlocks Hunt.
        </p>
        <div class="teams-row">
          <div class="team">
            <span v-if="mode !== 'duel'" class="team-label">TEAM A</span>
            <ArenaFighterSlot
              v-for="slot in slotsFor('A')"
              :key="slot"
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

          <div class="versus">
            <Transition name="countdown-pop" mode="out-in">
              <span v-if="isFighting && countdown > 0" :key="countdown" class="countdown-number">
                {{ countdown }}
              </span>
              <Icon v-else icon="mdi:sword-cross" class="versus-icon" />
            </Transition>
            <span v-if="countdown === 0" class="versus-text">VS</span>
          </div>

          <div class="team">
            <span v-if="mode !== 'duel'" class="team-label">{{
              mode === 'hunt' ? 'CREATURES' : 'TEAM B'
            }}</span>
            <template v-if="mode === 'hunt'">
              <ArenaCreatureSlot
                v-for="(slot, index) in creatureSlots"
                :key="slot?.key ?? 'creature-slot-' + index"
                :creature="slot"
                :can-change="canChangeFighters"
                :damage-numbers="damageForId(slot?.id ?? null)"
                :options="creaturePickerOptions"
                :picker-open="creaturePickerOpen && slot === null"
                @toggle-picker="toggleCreaturePicker"
                @clear="clearCreature"
                @select="selectCreature"
              />
            </template>
            <ArenaFighterSlot
              v-for="slot in slotsFor('B')"
              :key="slot"
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
        </div>
      </div>

      <!-- Bench: assigned dwellers not currently fighting -->
      <div v-if="bench.length" class="section">
        <h3 class="section-title">
          <Icon icon="mdi:account-group-outline" class="section-title-icon" />
          Bench
        </h3>
        <div class="roster-chips">
          <div
            v-for="entry in bench"
            :key="entry.id"
            class="roster-chip"
            :title="`HP ${entry.health}/${entry.max_health}`"
          >
            <div class="roster-chip-main">
              <DwellerPortrait
                :image-url="entry.image_url"
                :thumbnail-url="entry.thumbnail_url"
                :alt="entry.name"
                prefer-thumbnail
                image-class="h-8 w-8 shrink-0 rounded-full object-cover"
                fallback-class="h-8 w-8 text-theme-primary"
              />
              <span class="roster-name">{{ entry.name }}</span>
              <span class="roster-hp" :class="hpClass(entry)"
                >{{ entry.health }}/{{ entry.max_health }}</span
              >
            </div>
            <div class="roster-hp-bar">
              <Progress :model-value="hpPercent(entry)" class="h-1" :fill="hpFillColor(entry)" />
            </div>
            <TooltipProvider v-if="!isFighting" :delay-duration="200">
              <Tooltip>
                <TooltipTrigger as-child>
                  <Button
                    class="roster-remove"
                    size="icon-sm"
                    variant="ghost"
                    :aria-label="`Remove ${entry.name} from Arena`"
                    @click="unassign(entry)"
                  >
                    <Icon icon="mdi:close" class="h-4 w-4 text-danger" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Remove {{ entry.name }} from Arena</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </div>
      </div>

      <!-- Match result -->
      <div v-if="winnerName" class="result-banner finished">
        <Icon icon="mdi:trophy" class="result-icon" />
        <span v-if="roomState?.mode === 'duel'">MATCH COMPLETE &mdash; {{ winnerName }} wins!</span>
        <span v-else>MATCH COMPLETE &mdash; Victory for {{ winnerName }}!</span>
      </div>

      <!-- Post-battle actions -->
      <div v-if="isDone && injuredFighters.length" class="post-battle-actions">
        <Button variant="secondary" size="sm" :disabled="isHealing" @click="healInjured">
          <Icon v-if="isHealing" icon="mdi:loading" class="action-icon animate-spin" />
          <Icon v-else icon="mdi:medication" class="action-icon" />
          HEAL INJURED ({{ injuredFighters.length }})
        </Button>
      </div>

      <!-- Start fight -->
      <div v-if="canStart" class="fight-actions">
        <Button variant="default" :disabled="isStarting" @click="startFight">
          <Icon v-if="isStarting" icon="mdi:loading" class="fight-button-icon animate-spin" />
          <Icon v-else icon="mdi:sword-cross" class="fight-button-icon" />
          START FIGHT
        </Button>
      </div>

      <!-- Battle journal -->
      <div class="section">
        <div class="journal-header">
          <h3 class="section-title">
            <Icon icon="mdi:clipboard-text-clock-outline" class="section-title-icon" />
            Battle Journal
          </h3>
          <Button v-if="roomState?.events.length" variant="ghost" size="xs" @click="clearJournal"
            >CLEAR</Button
          >
        </div>
        <BattleLog :entries="journalEntries" empty-text="No rounds fought yet." />
      </div>

      <div class="arena-note">
        <Icon icon="mdi:information-outline" class="note-icon" />
        <span>
          Assign adult dwellers to the Arena room, pick the fighters for each side, then press START
          FIGHT. The winners gain happiness and XP, the losers lose happiness and are left standing
          at 1 HP. Change the fighters to start a new match.
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.arena-panel {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 1rem;
  margin: 0.5rem 0;
  background: var(--color-surface-sunken);
  border: 1px solid var(--color-surface-hover);
  border-radius: 8px;
}

.arena-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.arena-header-icon {
  width: 32px;
  height: 32px;
  color: var(--color-theme-primary);
}

.arena-title {
  font-size: 1.25rem;
  font-weight: bold;
  color: var(--color-theme-primary);
  margin: 0;
  letter-spacing: 0.1em;
}

.arena-subtitle {
  font-size: 0.75rem;
  color: var(--color-gray-500);
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.arena-badge {
  margin-left: auto;
  padding: 0.25rem 0.75rem;
  border: 1px solid var(--color-surface-hover);
  border-radius: 4px;
  font-size: 0.65rem;
  font-weight: bold;
  letter-spacing: 0.08em;
  color: var(--color-gray-400);
}

.arena-badge.ready {
  border-color: var(--color-theme-primary);
  color: var(--color-theme-primary);
}

.arena-badge.done {
  border-color: var(--color-warning);
  color: var(--color-warning);
}

/* Section pattern shared with the other room-modal sections */
.section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.875rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-theme-primary);
  margin: 0;
}

.section-title-icon {
  width: 0.875rem;
  height: 0.875rem;
}

.arena-content {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  padding: 0.5rem 0;
}

.roster-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.roster-chip {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.3rem 0.5rem;
  border: 1px solid var(--color-surface-hover);
  border-radius: 4px;
  font-size: 0.75rem;
  color: var(--color-gray-300);
}

.roster-chip-main {
  display: flex;
  align-items: baseline;
  gap: 0.4rem;
}

.roster-name {
  white-space: nowrap;
}

.roster-hp {
  font-size: 0.65rem;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.roster-hp.hp-healthy {
  color: var(--color-success);
}

.roster-hp.hp-low {
  color: var(--color-warning);
}

.roster-hp.hp-critical {
  color: var(--color-danger);
}

.roster-hp-bar {
  width: 48px;
}

.roster-remove {
  margin: -0.25rem;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.mode-select {
  display: flex;
  gap: 0.35rem;
}

.teams-row {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 1rem;
  align-items: center;
}

.team {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.team-label {
  text-align: center;
  font-size: 0.65rem;
  font-weight: bold;
  letter-spacing: 0.1em;
  color: var(--color-gray-500);
}

.versus {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
}

.countdown-number {
  font-size: 2.5rem;
  font-weight: bold;
  color: var(--color-danger);
  text-shadow: 0 0 12px rgba(255, 0, 0, 0.6);
  line-height: 1;
}

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

.fight-actions {
  display: flex;
  justify-content: center;
  padding: 0.25rem 0;
}

.fight-button-icon {
  width: 18px;
  height: 18px;
  margin-right: 0.4rem;
}

.journal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.4rem;
}

.versus-icon {
  width: 24px;
  height: 24px;
  color: var(--color-theme-primary);
}

.versus-text {
  font-size: 0.875rem;
  font-weight: bold;
  color: var(--color-theme-primary);
  letter-spacing: 0.1em;
}

.result-banner {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.6rem;
  border-radius: 4px;
  font-size: 0.875rem;
}

.result-banner.finished {
  background: color-mix(in srgb, var(--color-theme-primary) 12%, transparent);
  border: 1px solid var(--color-theme-primary);
  color: var(--color-theme-primary);
}

.result-icon {
  width: 18px;
  height: 18px;
}

.post-battle-actions {
  display: flex;
  justify-content: center;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.action-icon {
  width: 14px;
  height: 14px;
  margin-right: 0.3rem;
}

.arena-note {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  padding: 0.6rem;
  background: var(--color-surface-sunken);
  border: 1px solid var(--color-surface-hover);
  border-radius: 4px;
  font-size: 0.75rem;
  color: var(--color-gray-400);
  line-height: 1.5;
}

.note-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  color: var(--color-theme-primary);
}
</style>
