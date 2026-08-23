<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Icon } from '@iconify/vue'
import UButton from '@/core/components/ui/UButton.vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useToast } from '@/core/composables/useToast'
import {
  clearArenaEvents,
  fetchArenaState,
  setArenaFighters,
  startArenaFight,
  type ArenaFighter,
  type ArenaRosterEntry,
  type ArenaRoomState,
} from '../api/arena'

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

const roomState = ref<ArenaRoomState | null>(null)
const isLoading = ref(true)
const damageNumbers = ref<Array<{ id: number; side: 'A' | 'B'; amount: number }>>([])
const previousHp = ref<Record<string, number>>({})
const openPicker = ref<'A' | 'B' | null>(null)
let pollTimer: ReturnType<typeof setInterval> | null = null
let damageSeq = 0

const winnerName = computed(() => {
  const fighters = roomState.value?.fighters
  if (!roomState.value?.match_done || !fighters || fighters.length < 2) return null
  return fighters[0].health >= fighters[1].health ? fighters[0].name : fighters[1].name
})

const damageFor = (side: 'A' | 'B') => damageNumbers.value.filter((d) => d.side === side)

const recordDamage = (side: 'A' | 'B', fighter: ArenaFighter | null) => {
  if (!fighter) return
  const prev = previousHp.value[fighter.id]
  if (prev !== undefined && fighter.health < prev) {
    const entry = { id: ++damageSeq, side, amount: prev - fighter.health }
    damageNumbers.value.push(entry)
    setTimeout(() => {
      damageNumbers.value = damageNumbers.value.filter((d) => d.id !== entry.id)
    }, 900)
  }
  previousHp.value[fighter.id] = fighter.health
}

const applyState = (room: ArenaRoomState) => {
  recordDamage('A', room.fighters[0] ?? null)
  recordDamage('B', room.fighters[1] ?? null)
  const liveIds = new Set(room.fighters.map((f) => f.id))
  for (const id of Object.keys(previousHp.value)) {
    if (!liveIds.has(id)) delete previousHp.value[id]
  }
}

const load = async (silent = false) => {
  if (!authStore.token) return
  try {
    const state = await fetchArenaState(props.vaultId, authStore.token)
    const room = state.rooms.find((r) => r.room_id === props.roomId) ?? null
    roomState.value = room
    if (room) applyState(room)
    isLoading.value = false
  } catch {
    if (!silent) toast.error('Failed to load arena state')
    isLoading.value = false
  }
}

const startPolling = () => {
  stopPolling()
  pollTimer = setInterval(() => void load(true), 1000)
}

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

onMounted(() => {
  void load()
  startPolling()
})

onUnmounted(stopPolling)

const fighterA = computed(() => roomState.value?.fighters[0] ?? null)
const fighterB = computed(() => roomState.value?.fighters[1] ?? null)
const roster = computed(() => roomState.value?.roster ?? [])
const isReady = computed(() => roomState.value?.can_start ?? false)
const isDone = computed(() => roomState.value?.match_done ?? false)
const canStart = computed(() => roomState.value?.can_start ?? false)
const isFighting = computed(() => (roomState.value?.fight_started ?? false) && !isDone.value)
const canChangeFighters = computed(() => !isFighting.value)
const countdown = computed(() => roomState.value?.countdown_remaining ?? 0)
const isStarting = ref(false)

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
  try {
    await setArenaFighters(props.vaultId, props.roomId, fighterAId, fighterBId, authStore.token)
    openPicker.value = null
    previousHp.value = {}
    await load(true)
  } catch {
    toast.error('Failed to update fighters')
  }
}

const selectFighter = (slot: 'A' | 'B', entry: ArenaRosterEntry) => {
  const other = slot === 'A' ? validSlotId('B') : validSlotId('A')
  const a = slot === 'A' ? entry.id : other
  const b = slot === 'B' ? entry.id : other
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

const clearJournal = async () => {
  if (!authStore.token) return
  try {
    await clearArenaEvents(props.vaultId, props.roomId, authStore.token)
    await load(true)
  } catch {
    toast.error('Failed to clear the battle journal')
  }
}

const startFight = async () => {
  if (!authStore.token || !canStart.value || isStarting.value) return
  isStarting.value = true
  try {
    await startArenaFight(props.vaultId, props.roomId, authStore.token)
    previousHp.value = {}
    await load(true)
  } catch {
    toast.error('Failed to start fight')
  } finally {
    isStarting.value = false
  }
}

const healthPercent = (f: ArenaFighter | null) =>
  f ? Math.round((f.health / Math.max(1, f.max_health)) * 100) : 0

const combatPower = (f: ArenaFighter | null) => {
  if (!f) return 0
  return f.strength * 0.4 + f.endurance * 0.3 + f.agility * 0.3 + f.level * 2
}

const powerLabel = (f: ArenaFighter | null) => (f ? Math.round(combatPower(f)) : 0)

const journalIcon = (kind: string) => {
  switch (kind) {
    case 'hit':
      return 'mdi:sword'
    case 'finish':
      return 'mdi:skull-crossbones'
    case 'reward':
      return 'mdi:cash'
    default:
      return 'mdi:dots-horizontal'
  }
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
      <span class="arena-badge" :class="{ ready: isReady, done: isDone }">
        {{ isDone ? 'DONE' : isReady ? 'READY' : 'NEEDS 2 FIGHTERS' }}
      </span>
    </div>

    <div v-if="isLoading" class="loading">
      <div class="spinner">⚔️</div>
      <p>Loading arena...</p>
    </div>

    <div v-else class="arena-content">
      <!-- Mode selector -->
      <div class="mode-selector">
        <button class="mode-option active" type="button">
          <Icon icon="mdi:sword-cross" class="mode-icon" />
          DWELLER VS DWELLER
        </button>
        <button class="mode-option disabled" type="button" title="Coming soon">
          <Icon icon="mdi:paw" class="mode-icon" />
          DWELLER VS CREATURE
        </button>
        <button class="mode-option disabled" type="button" title="Coming soon">
          <Icon icon="mdi:trophy" class="mode-icon" />
          TOURNAMENT
        </button>
      </div>

      <!-- Fighters -->
      <div class="fighters-row">
        <div class="fighter-slot">
          <div v-if="fighterA" class="fighter-card">
            <button class="slot-clear" type="button" @click="clearFighter('A')">✕</button>
            <div class="damage-layer">
              <span v-for="d in damageFor('A')" :key="d.id" class="damage-number">-{{ d.amount }}</span>
            </div>
            <div class="fighter-portrait">{{ fighterA.name[0] }}</div>
            <div class="fighter-name">{{ fighterA.name }}</div>
            <div class="fighter-meta">Lv {{ fighterA.level }} &middot; POW {{ powerLabel(fighterA) }}</div>
            <div class="hp-track">
              <div class="hp-fill" :style="{ width: `${healthPercent(fighterA)}%` }"></div>
            </div>
            <div class="hp-text">{{ fighterA.health }}/{{ fighterA.max_health }}</div>
            <button v-if="canChangeFighters" class="slot-swap" type="button" @click="togglePicker('A')">SWAP</button>
          </div>
          <div v-else class="fighter-slot-empty" role="button" @click="togglePicker('A')">
            <span>+ PICK FIGHTER</span>
          </div>
          <div v-if="openPicker === 'A'" class="picker">
            <div v-for="entry in pickerOptions('A')" :key="entry.id" class="picker-option" @click="selectFighter('A', entry)">
              <span class="picker-name">{{ entry.name }}</span>
              <span class="picker-meta">Lv {{ entry.level }} &middot; {{ entry.health }} HP</span>
            </div>
            <div v-if="!pickerOptions('A').length" class="picker-empty">
              No available adults &mdash; assign dwellers to the Arena first.
            </div>
          </div>
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

        <div class="fighter-slot">
          <div v-if="fighterB" class="fighter-card">
            <button class="slot-clear" type="button" @click="clearFighter('B')">✕</button>
            <div class="damage-layer">
              <span v-for="d in damageFor('B')" :key="d.id" class="damage-number">-{{ d.amount }}</span>
            </div>
            <div class="fighter-portrait">{{ fighterB.name[0] }}</div>
            <div class="fighter-name">{{ fighterB.name }}</div>
            <div class="fighter-meta">Lv {{ fighterB.level }} &middot; POW {{ powerLabel(fighterB) }}</div>
            <div class="hp-track">
              <div class="hp-fill" :style="{ width: `${healthPercent(fighterB)}%` }"></div>
            </div>
            <div class="hp-text">{{ fighterB.health }}/{{ fighterB.max_health }}</div>
            <button v-if="canChangeFighters" class="slot-swap" type="button" @click="togglePicker('B')">SWAP</button>
          </div>
          <div v-else class="fighter-slot-empty" role="button" @click="togglePicker('B')">
            <span>+ PICK FIGHTER</span>
          </div>
          <div v-if="openPicker === 'B'" class="picker">
            <div v-for="entry in pickerOptions('B')" :key="entry.id" class="picker-option" @click="selectFighter('B', entry)">
              <span class="picker-name">{{ entry.name }}</span>
              <span class="picker-meta">Lv {{ entry.level }} &middot; {{ entry.health }} HP</span>
            </div>
            <div v-if="!pickerOptions('B').length" class="picker-empty">
              No available adults &mdash; assign dwellers to the Arena first.
            </div>
          </div>
        </div>
      </div>

      <!-- Assigned roster -->
      <div v-if="roster.length" class="arena-roster">
        <span class="roster-label">ASSIGNED</span>
        <div class="roster-chips">
          <div v-for="entry in roster" :key="entry.id" class="roster-chip" :class="{ fighting: isSelected(entry.id) }">
            <span class="roster-name">{{ entry.name }}</span>
            <button class="roster-remove" type="button" title="Remove from Arena" @click="unassign(entry)">✕</button>
          </div>
        </div>
      </div>

      <!-- Match result -->
      <div v-if="winnerName" class="result-banner finished">
        <Icon icon="mdi:trophy" class="result-icon" />
        <span>MATCH COMPLETE &mdash; {{ winnerName }} wins!</span>
      </div>

      <!-- Start fight -->
      <div v-if="canStart" class="fight-actions">
        <UButton variant="primary" size="md" :loading="isStarting" @click="startFight">
          <Icon icon="mdi:sword-cross" class="fight-button-icon" />
          START FIGHT
        </UButton>
      </div>

      <!-- Battle journal -->
      <div v-if="roomState?.events.length" class="battle-journal">
        <div class="journal-header">
          <Icon icon="mdi:clipboard-text-clock-outline" class="journal-icon" />
          <span>BATTLE JOURNAL</span>
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
      <UButton variant="secondary" size="sm" class="arena-destroy-btn" :disabled="isDestroying" @click="emit('destroy')">
        <Icon icon="mdi:delete" class="destroy-icon" />
        DESTROY
      </UButton>
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

.spinner {
  font-size: 2.5rem;
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

.arena-content {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  padding: 0.5rem 0;
}

.mode-selector {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.mode-option {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.35rem 0.7rem;
  border: 1px solid var(--color-surface-hover);
  border-radius: 4px;
  background: transparent;
  font-size: 0.7rem;
  font-weight: bold;
  letter-spacing: 0.05em;
  color: var(--color-gray-500);
  cursor: pointer;
}

.mode-option.active {
  border-color: var(--color-theme-primary);
  color: var(--color-theme-primary);
}

.mode-option.disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.mode-icon {
  width: 14px;
  height: 14px;
}

.fighter-slot {
  position: relative;
  display: flex;
  flex-direction: column;
}

.slot-clear {
  position: absolute;
  top: 4px;
  right: 6px;
  z-index: 3;
  border: none;
  background: transparent;
  color: var(--color-gray-500);
  font-size: 0.8rem;
  cursor: pointer;
}

.slot-clear:hover {
  color: var(--color-danger);
}

.slot-swap {
  margin-top: 0.35rem;
  padding: 0.2rem 0.6rem;
  border: 1px solid var(--color-surface-hover);
  border-radius: 4px;
  background: transparent;
  font-size: 0.65rem;
  font-weight: bold;
  letter-spacing: 0.05em;
  color: var(--color-theme-primary);
  cursor: pointer;
}

.fighter-slot-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 160px;
  padding: 1rem;
  border: 1px dashed var(--color-surface-hover);
  border-radius: 8px;
  color: var(--color-gray-500);
  font-size: 0.8rem;
  font-weight: bold;
  letter-spacing: 0.05em;
  cursor: pointer;
}

.fighter-slot-empty:hover {
  border-color: var(--color-theme-primary);
  color: var(--color-theme-primary);
}

.picker {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  z-index: 10;
  margin-top: 0.25rem;
  max-height: 160px;
  overflow-y: auto;
  background: var(--color-surface-raised);
  border: 1px solid var(--color-surface-hover);
  border-radius: 6px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
}

.picker-option {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
  padding: 0.45rem 0.6rem;
  cursor: pointer;
}

.picker-option:hover {
  background: var(--color-surface-hover);
}

.picker-name {
  font-size: 0.8rem;
  color: var(--color-theme-primary);
}

.picker-meta {
  font-size: 0.65rem;
  color: var(--color-gray-400);
}

.picker-empty {
  padding: 0.6rem;
  font-size: 0.7rem;
  color: var(--color-gray-500);
}

.arena-roster {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.roster-label {
  font-size: 0.65rem;
  font-weight: bold;
  letter-spacing: 0.1em;
  color: var(--color-gray-500);
}

.roster-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.roster-chip {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.25rem 0.5rem;
  border: 1px solid var(--color-surface-hover);
  border-radius: 9999px;
  font-size: 0.75rem;
  color: var(--color-gray-300);
}

.roster-chip.fighting {
  border-color: var(--color-theme-primary);
  color: var(--color-theme-primary);
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

.fighter-card {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.35rem;
  padding: 1rem;
  background: var(--color-surface-sunken);
  border: 1px solid var(--color-surface-hover);
  border-radius: 8px;
}

.damage-layer {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}

.damage-number {
  position: absolute;
  top: 10px;
  left: 50%;
  transform: translateX(-50%);
  color: var(--color-danger);
  font-weight: bold;
  font-size: 0.95rem;
  text-shadow: 0 0 8px rgba(255, 0, 0, 0.5);
  animation: damage-float 0.9s ease-out forwards;
  z-index: 2;
}

@keyframes damage-float {
  from {
    opacity: 1;
    transform: translate(-50%, 0);
  }
  to {
    opacity: 0;
    transform: translate(-50%, -32px);
  }
}

.fighter-card.vacant {
  opacity: 0.5;
}

.fighter-portrait {
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  border: 2px solid var(--color-theme-primary);
  background: var(--color-surface-raised);
  color: var(--color-theme-primary);
  font-size: 1.5rem;
  font-weight: bold;
}

.fighter-name {
  font-weight: 600;
  color: var(--color-theme-primary);
  text-align: center;
}

.fighter-meta {
  font-size: 0.7rem;
  color: var(--color-gray-400);
}

.hp-track {
  width: 100%;
  height: 10px;
  background: var(--color-surface-canvas);
  border: 1px solid var(--color-surface-hover);
  border-radius: 9999px;
  overflow: hidden;
}

.hp-fill {
  height: 100%;
  background: var(--color-theme-primary);
  transition: width 0.5s ease;
}

.hp-text {
  font-size: 0.7rem;
  color: var(--color-gray-400);
}

.vacant-text {
  color: var(--color-gray-500);
  font-size: 0.875rem;
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

.battle-journal {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  max-height: 180px;
  overflow-y: auto;
  padding: 0.6rem;
  background: var(--color-surface-sunken);
  border: 1px solid var(--color-surface-hover);
  border-radius: 6px;
}

.journal-header {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.7rem;
  font-weight: bold;
  letter-spacing: 0.1em;
  color: var(--color-gray-400);
  text-transform: uppercase;
}

.journal-icon {
  width: 16px;
  height: 16px;
  color: var(--color-theme-primary);
}

.journal-clear {
  margin-left: auto;
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