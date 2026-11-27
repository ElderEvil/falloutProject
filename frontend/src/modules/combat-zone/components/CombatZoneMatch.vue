<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import { Progress } from '@/core/components/ui/progress'
import ArenaRing from '@/modules/rooms/components/ArenaRing.vue'
import { useCombatPlayback } from '@/modules/combat/composables/useCombatPlayback'
import type { CombatPlaybackEvent, CombatPlaybackSnapshot } from '@/modules/combat/models/playback'
import type {
  CombatZoneMatchPartyRead,
  CombatZoneMatchRead,
  CombatZoneStance,
} from '../models/combatZone'
import { STANCE_OPTIONS } from '../models/combatZone'

const props = defineProps<{
  match: CombatZoneMatchRead
  viewerVaultId: string
  replay?: boolean
}>()

const emit = defineEmits<{
  (e: 'stance', stance: CombatZoneStance): void
  (e: 'back'): void
}>()

const viewerIsA = computed(() => props.match.party_a.vault_id === props.viewerVaultId)
const viewerIsB = computed(() => props.match.party_b.vault_id === props.viewerVaultId)
const isParticipant = computed(() => viewerIsA.value || viewerIsB.value)
const left = computed(() => props.match.party_a)
const right = computed(() => props.match.party_b)
const myStance = computed(() =>
  viewerIsA.value ? props.match.party_a.stance : props.match.party_b.stance
)
const isFinished = computed(() => props.match.status === 'finished')
const isDraw = computed(
  () => isFinished.value && !props.match.party_a.is_winner && !props.match.party_b.is_winner
)
const winnerSide = computed<'A' | 'B' | null>(() => {
  if (props.match.party_a.is_winner) return 'A'
  if (props.match.party_b.is_winner) return 'B'
  return null
})
const outcome = computed(() => {
  if (!isFinished.value) return 'Bout in progress'
  if (isDraw.value) return 'Draw — the purse is returned'
  if (isParticipant.value) {
    return (winnerSide.value === 'A') === viewerIsA.value ? 'Victory' : 'Defeat'
  }
  return `Vault ${winnerSide.value === 'A' ? left.value.vault_number : right.value.vault_number} wins`
})
const nextAttacker = computed(() => {
  const aNext = props.match.next_attack_party === 'A'
  if (isParticipant.value) {
    return (aNext && viewerIsA.value) || (!aNext && viewerIsB.value)
      ? 'You have the next turn'
      : 'The opponent has the next turn'
  }
  return `Vault ${aNext ? left.value.vault_number : right.value.vault_number} attacks next`
})
const allPlaybackEvents = computed<CombatPlaybackEvent[]>(() =>
  (props.match.events ?? []).map((event) => ({
    id: event.id,
    message: event.message,
    action: event.action ?? undefined,
  }))
)

const replayEvents = ref<CombatPlaybackEvent[]>([])
const replayTimers: ReturnType<typeof setTimeout>[] = []

function startReplay(): void {
  replayEvents.value = []
  allPlaybackEvents.value.forEach((event, index) => {
    replayTimers.push(
      setTimeout(() => {
        replayEvents.value = [...replayEvents.value, event]
      }, index * 700)
    )
  })
}

onMounted(() => {
  if (props.replay) startReplay()
})

onBeforeUnmount(() => {
  for (const timer of replayTimers) clearTimeout(timer)
})

function startingHealth(fighterId: string, fallback: number): number {
  for (const event of allPlaybackEvents.value) {
    const target = event.action?.targets?.find(
      (impact) => impact.target_id === fighterId && impact.health_before != null
    )
    if (target?.health_before != null) return target.health_before
  }
  return fallback
}

const replayHealth = computed(() => {
  const health: Record<string, number> = {
    [props.match.party_a.fighter.id]: startingHealth(
      props.match.party_a.fighter.id,
      props.match.party_a.fighter.health
    ),
    [props.match.party_b.fighter.id]: startingHealth(
      props.match.party_b.fighter.id,
      props.match.party_b.fighter.health
    ),
  }
  for (const event of replayEvents.value) {
    for (const impact of event.action?.targets ?? []) {
      if (impact.health_after != null) health[impact.target_id] = impact.health_after
    }
  }
  return health
})

const playbackSource = computed<CombatPlaybackSnapshot | null>(() => {
  const match = props.match
  return {
    key: match.id,
    health: props.replay
      ? replayHealth.value
      : {
          [match.party_a.fighter.id]: match.party_a.fighter.health,
          [match.party_b.fighter.id]: match.party_b.fighter.health,
        },
    events: props.replay ? replayEvents.value : allPlaybackEvents.value,
  }
})

const { health, active, phase, damageNumbers } = useCombatPlayback(() => playbackSource.value)

const playedFighter = (party: CombatZoneMatchPartyRead) => ({
  ...party.fighter,
  health: health.value[party.fighter.id] ?? party.fighter.health,
})

const ringState = computed(() => ({
  team_a: [playedFighter(props.match.party_a)],
  team_b: [playedFighter(props.match.party_b)],
  match_done: isFinished.value,
  fight_started: true,
  next_attack_team: props.match.next_attack_party as 'A' | 'B',
}))

const events = computed(() => (props.match.events ?? []).slice(-12))

function currentHealth(party: CombatZoneMatchPartyRead): number {
  return health.value[party.fighter.id] ?? party.fighter.health
}

function hpPercent(party: CombatZoneMatchPartyRead): number {
  if (party.fighter.max_health <= 0) return 0
  return Math.max(0, Math.min(100, (currentHealth(party) / party.fighter.max_health) * 100))
}

function displayName(party: CombatZoneMatchPartyRead, isMine: boolean): string {
  return isMine ? party.fighter.name : `Vault ${party.vault_number}`
}

function eventTime(iso: string | null | undefined): string {
  if (!iso) return ''
  const date = new Date(iso)
  return Number.isNaN(date.getTime())
    ? ''
    : date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}
</script>

<template>
  <section class="space-y-4">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <p class="text-xs tracking-[0.25em] text-theme-primary/60">
          INTERCHANGE 77 // REGULATION BOUT
        </p>
        <h3 class="text-xl font-bold text-theme-primary terminal-glow">{{ outcome }}</h3>
      </div>
      <Button variant="outline" size="sm" @click="emit('back')">
        <Icon icon="mdi:arrow-left" class="mr-1 size-4" />
        Back to the board
      </Button>
    </div>

    <ArenaRing
      :state="ringState"
      :skill-enabled="false"
      :damage-numbers="damageNumbers"
      :active-action="active"
      :combat-phase="phase"
      :attacking-fighter-id="active?.action.actor_id ?? null"
      heading="Interchange 77 regulation bout"
    />

    <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
      <article class="rounded border border-theme-primary/30 bg-surface-raised/60 p-4">
        <p class="text-xs uppercase tracking-widest text-theme-primary/60">
          {{ viewerIsA ? 'Your contender' : 'Contender A' }}
        </p>
        <p class="truncate text-lg font-bold text-theme-primary">
          {{ displayName(left, viewerIsA) }}
        </p>
        <p class="text-xs text-theme-primary/60">
          Vault {{ left.vault_number }} · LVL {{ left.fighter.level }} ·
          {{ Math.round(left.fighter.power) }} power
        </p>
        <Progress :model-value="hpPercent(left)" class="mt-3 h-2" />
        <p class="mt-1 text-xs text-theme-primary/70">
          {{ currentHealth(left) }} / {{ left.fighter.max_health }} HP
          <span v-if="left.credited_caps !== null"> · {{ left.credited_caps }} caps credited</span>
        </p>
        <p v-if="viewerIsA" class="mt-3 text-xs text-theme-primary/60">Stance: {{ left.stance }}</p>
        <p v-else class="mt-3 text-xs text-theme-primary/60">Stance: hidden by the Umpire</p>
      </article>

      <article class="rounded border border-theme-primary/30 bg-surface-raised/60 p-4">
        <p class="text-xs uppercase tracking-widest text-theme-primary/60">
          {{ viewerIsB ? 'Your contender' : 'Contender B' }}
        </p>
        <p class="truncate text-lg font-bold text-theme-primary">
          {{ displayName(right, viewerIsB) }}
        </p>
        <p class="text-xs text-theme-primary/60">
          Vault {{ right.vault_number }} · LVL {{ right.fighter.level }} ·
          {{ Math.round(right.fighter.power) }} power
        </p>
        <Progress :model-value="hpPercent(right)" class="mt-3 h-2" />
        <p class="mt-1 text-xs text-theme-primary/70">
          {{ currentHealth(right) }} / {{ right.fighter.max_health }} HP
          <span v-if="right.credited_caps !== null">
            · {{ right.credited_caps }} caps credited</span
          >
        </p>
        <p v-if="viewerIsB" class="mt-3 text-xs text-theme-primary/60">
          Stance: {{ right.stance }}
        </p>
        <p v-else class="mt-3 text-xs text-theme-primary/60">Stance: hidden by the Umpire</p>
      </article>
    </div>

    <div
      class="flex flex-wrap items-center gap-3 rounded border border-theme-primary/20 bg-surface-sunken/40 px-4 py-2 text-xs text-theme-primary/70"
    >
      <span>Purse <strong class="text-theme-primary">{{ match.pot_caps }}</strong> caps</span>
      <span>Round {{ match.round_seq }}</span>
      <span v-if="!isFinished">{{ nextAttacker }}</span>
      <span v-else>Finished · {{ match.finish_reason ?? 'regulation' }}</span>
    </div>

    <div v-if="isParticipant && !isFinished" class="space-y-2">
      <p class="text-xs uppercase tracking-widest text-theme-primary/60">Command the next round</p>
      <div class="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Button
          v-for="option in STANCE_OPTIONS"
          :key="option.value"
          :variant="myStance === option.value ? 'default' : 'outline'"
          size="sm"
          :title="option.hint"
          @click="emit('stance', option.value)"
        >
          <Icon :icon="option.icon" class="mr-1 size-4" />
          {{ option.label }}
        </Button>
      </div>
    </div>

    <div class="space-y-2">
      <p class="text-xs uppercase tracking-widest text-theme-primary/60">The frequency remembers</p>
      <ol
        class="max-h-56 space-y-1 overflow-y-auto rounded border border-theme-primary/20 bg-surface-sunken/30 p-3"
      >
        <li v-for="event in events" :key="event.id" class="text-xs text-theme-primary/80">
          <span class="mr-2 text-theme-primary/40">{{ eventTime(event.created_at) }}</span>
          {{ event.message }}
        </li>
        <li v-if="events.length === 0" class="text-xs text-theme-primary/50">
          The bell has not rung yet.
        </li>
      </ol>
    </div>
  </section>
</template>
