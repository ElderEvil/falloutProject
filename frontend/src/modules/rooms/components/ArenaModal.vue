<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Icon } from '@iconify/vue'
import UButton from '@/core/components/ui/UButton.vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useToast } from '@/core/composables/useToast'
import { usePolling } from '@/core/composables/usePolling'
import ArenaFighterSlot from './ArenaFighterSlot.vue'
import { useArenaStore } from '../stores/arena'
import { useDwellerMedicalStore } from '@/modules/dwellers/stores/dwellerMedical'
import type { ArenaFighter, ArenaRosterEntry } from '../api/arena'

interface Props {
  vaultId: string
  roomId: string
  isDestroying?: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  destroy: []
}>()

const authStore = useAuthStore()
const toast = useToast()
const { management: dwellerManagementStore } = useDwellerStore()
const medicalStore = useDwellerMedicalStore()
const arenaStore = useArenaStore()

const isLoading = ref(true)
const damageNumbers = ref<Array<{ id: number; side: 'A' | 'B'; amount: number }>>([])
const previousHp = ref<Record<string, number>>({})
const openPicker = ref<'A' | 'B' | null>(null)
const isStarting = ref(false)
let damageSeq = 0
const pendingDamageTimers = new Set<ReturnType<typeof setTimeout>>()

onUnmounted(() => {
  for (const timer of pendingDamageTimers) clearTimeout(timer)
  pendingDamageTimers.clear()
})

const roomState = computed(() => arenaStore.getRoom(props.roomId))

const winnerName = computed(() => roomState.value?.winner_name ?? null)

const damageFor = (side: 'A' | 'B') => damageNumbers.value.filter((d) => d.side === side)

const recordDamage = (side: 'A' | 'B', fighter: ArenaFighter | null) => {
  if (!fighter) return
  const prev = previousHp.value[fighter.id]
  if (prev !== undefined && fighter.health < prev) {
    const entry = { id: ++damageSeq, side, amount: prev - fighter.health }
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
  const fighters = roomState.value?.fighters ?? []
  recordDamage('A', fighters[0] ?? null)
  recordDamage('B', fighters[1] ?? null)
  const liveIds = new Set(fighters.map((f) => f.id))
  for (const id of Object.keys(previousHp.value)) {
    if (!liveIds.has(id)) delete previousHp.value[id]
  }
}

const load = async (silent = false) => {
  if (!authStore.token) return
  await arenaStore.fetchState(props.vaultId, authStore.token, silent)
  applyState()
  isLoading.value = false
}

onMounted(() => {
  void load()
})

usePolling(() => load(true), { interval: 1_000, immediate: false })

const fighterA = computed(() => roomState.value?.fighters[0] ?? null)
const fighterB = computed(() => roomState.value?.fighters[1] ?? null)
const roster = computed(() => roomState.value?.roster ?? [])
// The bench is the assigned dwellers NOT currently in a slot — every dweller
// appears exactly once: fighters on the stage (slots), the rest here.
const bench = computed(() => roster.value.filter((entry) => !isSelected(entry.id)))
const isDone = computed(() => roomState.value?.match_done ?? false)
const canStart = computed(() => roomState.value?.can_start ?? false)
const isFighting = computed(() => (roomState.value?.fight_started ?? false) && !isDone.value)
const canChangeFighters = computed(() => !isFighting.value)
const countdown = computed(() => roomState.value?.countdown_remaining ?? 0)

const isSelected = (id: string) =>
  roomState.value?.fighter_a_id === id || roomState.value?.fighter_b_id === id

const rosterIds = computed(() => new Set(roster.value.map((entry) => entry.id)))

const validSlotId = (slot: 'A' | 'B') => {
  const id = slot === 'A' ? roomState.value?.fighter_a_id : roomState.value?.fighter_b_id
  return id && rosterIds.value.has(id) ? id : null
}

const pickerOptions = (slot: 'A' | 'B') => {
  const otherId = slot === 'A' ? roomState.value?.fighter_b_id : roomState.value?.fighter_a_id
  return roster.value.filter((entry) => entry.id !== otherId)
}

const togglePicker = (slot: 'A' | 'B') => {
  if (isFighting.value) return
  openPicker.value = openPicker.value === slot ? null : slot
}

const persistFighters = async (fighterAId: string | null, fighterBId: string | null) => {
  if (!authStore.token) return
  const ok = await arenaStore.setFighters(props.vaultId, props.roomId, fighterAId, fighterBId, authStore.token)
  if (ok) {
    openPicker.value = null
    previousHp.value = {}
  }
}

const selectFighter = (slot: 'A' | 'B', entry: ArenaRosterEntry) => {
  const other = slot === 'A' ? validSlotId('B') : validSlotId('A')
  let a = slot === 'A' ? entry.id : other
  let b = slot === 'B' ? entry.id : other

  // Smart pairing: when the opposite slot is empty and exactly one candidate
  // remains, fill it — picking the first of two fighters almost always means
  // the second belongs in the other corner.
  const opposite = slot === 'A' ? b : a
  if (!opposite) {
    const taken = new Set([a, b].filter((id): id is string => !!id))
    const remaining = roster.value.filter((e) => !taken.has(e.id))
    if (remaining.length === 1) {
      if (slot === 'A') b = remaining[0].id
      else a = remaining[0].id
    }
  }

  void persistFighters(a, b)
}

const clearFighter = (slot: 'A' | 'B') => {
  const other = slot === 'A' ? validSlotId('B') : validSlotId('A')
  const a = slot === 'A' ? null : other
  const b = slot === 'B' ? null : other
  void persistFighters(a, b)
}

const unassign = async (entry: ArenaRosterEntry) => {
  if (!authStore.token) return
  try {
    await dwellerManagementStore.unassignDwellerFromRoom(entry.id, authStore.token)
  } catch {
    toast.error('Failed to remove dweller from the Arena')
  }
}

// Post-battle conveniences: patch up the loser, clear the room for the next
// match. Fighters under 50% HP are the ones a stimpack actually helps.
const injuredFighters = computed(() =>
  (roomState.value?.fighters ?? []).filter(
    (fighter: ArenaFighter) => fighter.max_health > 0 && fighter.health / fighter.max_health < 0.5
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

const isUnassigningAll = ref(false)
const unassignAll = async () => {
  if (!authStore.token || isUnassigningAll.value || !roster.value.length) return
  isUnassigningAll.value = true
  try {
    for (const entry of roster.value) {
      try {
        await dwellerManagementStore.unassignDwellerFromRoom(entry.id, authStore.token)
      } catch {
        toast.error(`Failed to remove ${entry.name} from the Arena`)
      }
    }
    previousHp.value = {}
    await load(true)
  } finally {
    isUnassigningAll.value = false
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

const journalIcon = (kind: string) => {
  switch (kind) {
    case 'hit':
      return 'mdi:sword'
    case 'finish':
      return 'mdi:skull-crossbones'
    case 'reward':
      return 'mdi:emoticon-happy-outline'
    default:
      return 'mdi:dots-horizontal'
  }
}

const hpPercent = (entry: ArenaRosterEntry) =>
  entry.max_health > 0 ? Math.round((entry.health / entry.max_health) * 100) : 0

const hpClass = (entry: ArenaRosterEntry) => {
  const pct = hpPercent(entry)
  if (pct < 25) return 'hp-critical'
  if (pct < 50) return 'hp-low'
  return 'hp-healthy'
}
</script>

<template>
  <div class="arena-panel">
    <div class="arena-header">
      <Icon icon="mdi:sword-cross" class="arena-header-icon" />
      <div>
        <h2 class="arena-title">ARENA</h2>
        <p class="arena-subtitle">{{ roomState?.room_name ?? 'Arena' }} &middot; Tier {{ roomState?.tier ?? 1 }}</p>
      </div>
      <span class="arena-badge" :class="{ ready: canStart, done: isDone }">
        {{ isDone ? 'DONE' : canStart ? 'READY' : 'NEEDS 2 FIGHTERS' }}
      </span>
    </div>

    <div v-if="isLoading" class="loading">
      <Icon icon="mdi:sword-cross" class="loading-icon spin" />
      <p>Loading arena...</p>
    </div>

    <div v-else class="arena-content">
      <!-- Fighters -->
      <div class="section">
        <h3 class="section-title">
          <Icon icon="mdi:sword-cross" class="section-title-icon" />
          Fighters
        </h3>
        <div class="fighters-row">
          <ArenaFighterSlot
            side="A"
            :fighter="fighterA"
            :can-change="canChangeFighters"
            :damage-numbers="damageFor('A')"
            :options="pickerOptions('A')"
            :picker-open="openPicker === 'A'"
            @toggle-picker="togglePicker"
            @clear="clearFighter"
            @select="selectFighter"
          />

          <div class="versus">
            <Transition name="countdown-pop" mode="out-in">
              <span v-if="isFighting && countdown > 0" :key="countdown" class="countdown-number">
                {{ countdown }}
              </span>
              <Icon v-else icon="mdi:sword-cross" class="versus-icon" />
            </Transition>
            <span v-if="countdown === 0" class="versus-text">VS</span>
          </div>

          <ArenaFighterSlot
            side="B"
            :fighter="fighterB"
            :can-change="canChangeFighters"
            :damage-numbers="damageFor('B')"
            :options="pickerOptions('B')"
            :picker-open="openPicker === 'B'"
            @toggle-picker="togglePicker"
            @clear="clearFighter"
            @select="selectFighter"
          />
        </div>
      </div>

      <!-- Bench: assigned dwellers not currently fighting -->
      <div v-if="bench.length" class="section">
        <h3 class="section-title">
          <Icon icon="mdi:account-group-outline" class="section-title-icon" />
          Bench
        </h3>
        <div class="roster-chips">
          <div v-for="entry in bench" :key="entry.id" class="roster-chip" :title="`HP ${entry.health}/${entry.max_health}`">
            <div class="roster-chip-main">
              <span class="roster-name">{{ entry.name }}</span>
              <span class="roster-hp" :class="hpClass(entry)">{{ entry.health }}/{{ entry.max_health }}</span>
            </div>
            <div class="roster-hp-bar">
              <div class="roster-hp-fill" :class="hpClass(entry)" :style="{ width: hpPercent(entry) + '%' }"></div>
            </div>
            <button
              v-if="!isFighting"
              class="roster-remove"
              type="button"
              :aria-label="`Remove ${entry.name} from Arena`"
              title="Remove from Arena"
              @click="unassign(entry)"
            >
              ✕
            </button>
          </div>
        </div>
      </div>

      <!-- Match result -->
      <div v-if="winnerName" class="result-banner finished">
        <Icon icon="mdi:trophy" class="result-icon" />
        <span>MATCH COMPLETE &mdash; {{ winnerName }} wins!</span>
      </div>

      <!-- Post-battle actions -->
      <div v-if="isDone && injuredFighters.length" class="post-battle-actions">
        <UButton
          variant="secondary"
          size="sm"
          :loading="isHealing"
          @click="healInjured"
        >
          <Icon icon="mdi:medication" class="action-icon" />
          HEAL INJURED ({{ injuredFighters.length }})
        </UButton>
      </div>

      <!-- Start fight -->
      <div v-if="canStart" class="fight-actions">
        <UButton variant="primary" size="md" :loading="isStarting" @click="startFight">
          <Icon icon="mdi:sword-cross" class="fight-button-icon" />
          START FIGHT
        </UButton>
      </div>

      <!-- Battle journal -->
      <div v-if="roomState?.events.length" class="section">
        <div class="journal-header">
          <h3 class="section-title">
            <Icon icon="mdi:clipboard-text-clock-outline" class="section-title-icon" />
            Battle Journal
          </h3>
          <button class="journal-clear" type="button" @click="clearJournal">CLEAR</button>
        </div>
        <div class="journal-list">
          <div v-for="event in roomState.events" :key="event.id" class="journal-entry" :class="event.kind">
            <Icon :icon="journalIcon(event.kind)" class="journal-entry-icon" />
            <span>{{ event.message }}</span>
          </div>
        </div>
      </div>

      <div class="arena-note">
        <Icon icon="mdi:information-outline" class="note-icon" />
        <span>
          Assign adult dwellers to the Arena room, pick two fighters, then press
          START FIGHT. The winner gains happiness and XP, the loser loses
          happiness and is left standing at 1 HP. Change the fighters to start a
          new match.
        </span>
      </div>
    </div>

    <div class="arena-footer">
      <span class="footer-note">Fights resolve automatically — watch the HP bars.</span>
      <div class="footer-actions">
        <UButton
          variant="secondary"
          size="sm"
          :loading="isUnassigningAll"
          :disabled="isFighting || !roster.length"
          @click="unassignAll"
        >
          <Icon icon="mdi:account-remove" class="destroy-icon" />
          UNASSIGN ALL
        </UButton>
        <UButton variant="secondary" size="sm" class="arena-destroy-btn" :disabled="isDestroying" @click="emit('destroy')">
          <Icon icon="mdi:delete" class="destroy-icon" />
          DESTROY
        </UButton>
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

.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
  padding: 3rem;
  color: var(--color-theme-primary);
}

.loading-icon {
  width: 2.5rem;
  height: 2.5rem;
}

.spin {
  animation: spin 2s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
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
  height: 4px;
  border-radius: 2px;
  background: rgba(128, 128, 128, 0.25);
  overflow: hidden;
}

.roster-hp-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.3s ease;
}

.roster-hp-fill.hp-healthy {
  background: var(--color-success);
}

.roster-hp-fill.hp-low {
  background: var(--color-warning);
}

.roster-hp-fill.hp-critical {
  background: var(--color-danger);
}

.roster-remove {
  border: none;
  background: transparent;
  color: var(--color-gray-500);
  font-size: 0.7rem;
  cursor: pointer;
}

.roster-remove:hover {
  color: var(--color-danger);
}

.fighters-row {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 1rem;
  align-items: center;
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
  transition: opacity 0.3s ease, transform 0.3s ease;
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

.journal-list {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  max-height: 180px;
  overflow-y: auto;
  padding: 0.6rem;
  background: var(--color-surface-sunken);
  border: 1px solid var(--color-surface-hover);
  border-radius: 4px;
}

.journal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.4rem;
}

.journal-clear {
  border: 1px solid var(--color-surface-hover);
  border-radius: 4px;
  padding: 0.1rem 0.5rem;
  background: transparent;
  font-size: 0.6rem;
  font-weight: bold;
  letter-spacing: 0.05em;
  color: var(--color-gray-400);
  cursor: pointer;
}

.journal-clear:hover {
  color: var(--color-theme-primary);
  border-color: var(--color-theme-primary);
}

.journal-list {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.journal-entry {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.8rem;
  color: var(--color-gray-300);
  line-height: 1.35;
}

.journal-entry-icon {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
  color: var(--color-gray-500);
}

.journal-entry.finish .journal-entry-icon {
  color: var(--color-danger);
}

.journal-entry.finish {
  color: var(--color-theme-primary);
  font-weight: 600;
}

.journal-entry.reward .journal-entry-icon {
  color: var(--color-caps);
}

.journal-entry.reward {
  color: var(--color-caps);
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

.arena-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.footer-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-left: auto;
}

.footer-note {
  font-size: 0.75rem;
  color: var(--color-gray-500);
}

.arena-destroy-btn {
  margin-left: auto;
}

.destroy-icon {
  width: 14px;
  height: 14px;
  margin-right: 0.3rem;
}
</style>
