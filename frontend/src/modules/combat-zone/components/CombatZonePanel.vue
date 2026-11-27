<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { useNow } from '@/core/composables/useNow'
import { Button } from '@/core/components/ui/button'
import TerminalModal from '@/core/components/common/TerminalModal.vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { DWELLER_LIST_CHANGED_MESSAGE } from '@/modules/dwellers/stores/dwellerFilter'
import { isMature } from '@/modules/dwellers/models/dweller'
import { formatRemaining } from '@/modules/exploration/composables/useExplorationProgress'
import type { CombatZoneMarkerRead } from '@/modules/map/models/map'
import { useCombatZoneStore } from '../stores/combatZone'
import {
  STANCE_OPTIONS,
  isPartyDeployed,
  partyStatusLabel,
  secondsUntil,
  type CombatZoneLobbyParty,
  type CombatZoneStance,
} from '../models/combatZone'
import CombatZoneMatch from './CombatZoneMatch.vue'

const props = defineProps<{
  vaultId: string
  marker: CombatZoneMarkerRead | null
  initialMatchId?: string | null
}>()

const open = defineModel<boolean>('open', { required: true })

const authStore = useAuthStore()
const vaultStore = useVaultStore()
const { filter: dwellerStore } = useDwellerStore()
const combatZone = useCombatZoneStore()

const tab = ref<'overview' | 'board'>('overview')
const selectedDwellerId = ref<string | null>(null)
const replaying = ref(false)
const rosterError = ref<string | null>(null)
const now = useNow(1000)

const party = computed(() => combatZone.party)
const match = computed(() => combatZone.match)
const isDeployed = computed(() => isPartyDeployed(party.value))
const resultOnly = computed(() => !props.marker?.enabled && Boolean(props.initialMatchId))
const vaultNumber = computed(() => vaultStore.loadedVaults[props.vaultId]?.number ?? null)
const myVaultNumber = computed(() => party.value?.vault_number ?? vaultNumber.value)
const caps = computed(() => vaultStore.loadedVaults[props.vaultId]?.bottle_caps ?? null)
const fee = computed(() => combatZone.lobby?.entry_fee_caps ?? null)

const eligibleDwellers = computed(() =>
  dwellerStore.allDwellers.filter(
    (dweller) =>
      isMature(dweller) &&
      dweller.status !== 'dead' &&
      (dweller.status === 'idle' || dweller.status === 'working')
  )
)

const selectedDweller = computed(
  () => eligibleDwellers.value.find((dweller) => dweller.id === selectedDwellerId.value) ?? null
)

const canSend = computed(
  () =>
    Boolean(props.marker?.enabled) &&
    !isDeployed.value &&
    selectedDweller.value !== null &&
    !combatZone.isLoading &&
    (fee.value === null || caps.value === null || caps.value >= fee.value)
)

const etaSeconds = computed(() => secondsUntil(party.value?.arrives_at, now.value))
const eta = computed(() => {
  if (!party.value?.arrives_at) return null
  if (etaSeconds.value <= 0) return 'arriving now'
  if (etaSeconds.value < 60) return `${etaSeconds.value}s`
  return formatRemaining(etaSeconds.value)
})

let etaRefreshSent = false
watch(etaSeconds, (remaining) => {
  if (remaining > 0) {
    etaRefreshSent = false
    return
  }
  if (party.value?.status === 'traveling' && !etaRefreshSent) {
    etaRefreshSent = true
    void combatZone.refresh()
  }
})

const canCommandStance = computed(
  () => party.value?.status === 'queued' || party.value?.status === 'in_match'
)

function defaultSelection(): void {
  if (
    selectedDwellerId.value &&
    eligibleDwellers.value.some((d) => d.id === selectedDwellerId.value)
  ) {
    return
  }
  selectedDwellerId.value = eligibleDwellers.value[0]?.id ?? null
}

async function load(): Promise<void> {
  const token = authStore.token
  if (!open.value || !token) return
  rosterError.value = null
  await combatZone.open(props.vaultId, token)
  try {
    await dwellerStore.fetchAllDwellers(props.vaultId, true)
  } catch (err) {
    if (err instanceof Error && err.message === DWELLER_LIST_CHANGED_MESSAGE) {
      rosterError.value = `Roster for vault ${props.vaultId} changed while loading. Retry.`
    }
  }
  if (props.initialMatchId) await combatZone.watchMatch(props.initialMatchId)
  defaultSelection()
}

watch(
  open,
  (isOpen) => {
    if (isOpen) {
      void load()
    } else {
      replaying.value = false
      rosterError.value = null
      etaRefreshSent = false
      combatZone.close()
      selectedDwellerId.value = null
      tab.value = 'overview'
    }
  },
  { immediate: true }
)

watch(
  () => props.vaultId,
  (next, previous) => {
    if (next === previous) return
    replaying.value = false
    rosterError.value = null
    etaRefreshSent = false
    selectedDwellerId.value = null
    tab.value = 'overview'
    if (!open.value) return
    combatZone.close()
    void load()
  }
)

watch(
  () => props.marker?.enabled,
  (enabled) => {
    if (open.value && (enabled || props.initialMatchId)) void load()
  }
)

watch(
  () => props.initialMatchId,
  (matchId) => {
    if (!open.value || !matchId) return
    if (combatZone.lobby) void combatZone.watchMatch(matchId)
    else void load()
  }
)

watch(eligibleDwellers, () => defaultSelection())

onBeforeUnmount(() => combatZone.close())

async function send(): Promise<void> {
  if (!selectedDwellerId.value) return
  const ok = await combatZone.sendParty(selectedDwellerId.value)
  if (ok) selectedDwellerId.value = null
}

async function challenge(target: CombatZoneLobbyParty): Promise<void> {
  if (target.vault_number === myVaultNumber.value) return
  await combatZone.challenge(target.party_id)
}

function commandStance(stance: CombatZoneStance): void {
  void combatZone.setStance(stance)
}

function backToLobby(): void {
  replaying.value = false
  combatZone.backToLobby()
}

function closePanel(): void {
  open.value = false
}
</script>

<template>
  <TerminalModal
    v-model:open="open"
    title="The Combat Zone"
    icon="mdi:sword-cross"
    size="5xl"
    max-height="90"
    body-class="flex-1 space-y-4 overflow-y-auto p-5"
  >
    <div class="rounded border border-theme-primary/25 bg-theme-primary/5 p-4">
      <p class="text-xs tracking-[0.25em] text-theme-primary/60">
        INTERCHANGE 77 // EMERGENCY BAND
      </p>
      <p class="mt-2 text-sm text-theme-primary/85">
        “Attention, municipal units. Interchange 77 is now accepting contenders. Please have your
        purse ready.”
      </p>
      <p class="mt-1 text-xs text-theme-primary/50">
        — Unit 77, Traffic Adjudication. Known to the wasteland as the Umpire.
      </p>
    </div>

    <div
      v-if="!marker?.enabled && !resultOnly"
      class="rounded border border-theme-primary/25 bg-surface-sunken/40 p-6 text-center"
    >
      <Icon icon="mdi:radio-off" class="mx-auto size-8 text-theme-primary/50" />
      <p class="mt-2 text-sm font-bold text-theme-primary">The signal is dark.</p>
      <p class="mt-1 text-xs text-theme-primary/60">
        The Umpire is not accepting contenders from this vault yet.
      </p>
    </div>

    <template v-else>
      <CombatZoneMatch
        v-if="match"
        :key="`${match.id}:${replaying ? 'replay' : 'live'}`"
        :match="match"
        :viewer-vault-id="vaultId"
        :replay="replaying"
        @stance="commandStance"
        @back="backToLobby"
      />

      <template v-else>
        <div class="flex gap-2 border-b border-theme-primary/20 pb-2">
          <Button
            :variant="tab === 'overview' ? 'default' : 'ghost'"
            size="sm"
            @click="tab = 'overview'"
          >
            <Icon icon="mdi:account-star" class="mr-1 size-4" />
            Contender
          </Button>
          <Button :variant="tab === 'board' ? 'default' : 'ghost'" size="sm" @click="tab = 'board'">
            <Icon icon="mdi:radio-tower" class="mr-1 size-4" />
            The frequency
            <span v-if="combatZone.lobby?.active_matches.length" class="ml-1 text-xs text-success">
              {{ combatZone.lobby.active_matches.length }} live
            </span>
          </Button>
        </div>

        <p
          v-if="combatZone.error"
          class="rounded border border-status-fighting/40 bg-status-fighting/10 p-3 text-xs text-status-fighting"
        >
          {{ combatZone.error }}
        </p>
        <p
          v-if="rosterError"
          class="rounded border border-status-fighting/40 bg-status-fighting/10 p-3 text-xs text-status-fighting"
        >
          {{ rosterError }}
        </p>

        <section v-if="tab === 'overview'" class="space-y-4">
          <div
            v-if="isDeployed && party"
            class="rounded border border-theme-primary/30 bg-surface-raised/60 p-4"
          >
            <div class="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p class="text-xs uppercase tracking-widest text-theme-primary/60">
                  Registered contender
                </p>
                <p class="text-lg font-bold text-theme-primary">{{ party.dweller_name }}</p>
                <p class="text-xs text-theme-primary/60">
                  Vault {{ party.vault_number }} · LVL {{ party.level }} ·
                  {{ Math.round(party.power) }} power
                </p>
              </div>
              <span
                class="rounded border border-theme-primary/30 px-2 py-1 text-xs text-theme-primary/80"
              >
                {{ partyStatusLabel(party.status) }}
              </span>
            </div>

            <div class="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-theme-primary/70">
              <span>HP {{ party.health }} / {{ party.max_health }}</span>
              <span>Purse {{ party.escrow_caps }}</span>
              <span v-if="eta">ETA {{ eta }}</span>
              <span v-else>At the interchange</span>
            </div>

            <div v-if="canCommandStance" class="mt-4 space-y-2">
              <p class="text-xs uppercase tracking-widest text-theme-primary/60">Command</p>
              <div class="grid grid-cols-2 gap-2 sm:grid-cols-4">
                <Button
                  v-for="option in STANCE_OPTIONS"
                  :key="option.value"
                  :variant="party.stance === option.value ? 'default' : 'outline'"
                  size="sm"
                  :title="option.hint"
                  @click="commandStance(option.value)"
                >
                  <Icon :icon="option.icon" class="mr-1 size-4" />
                  {{ option.label }}
                </Button>
              </div>
            </div>

            <div class="mt-4">
              <Button
                variant="outline"
                size="sm"
                :disabled="combatZone.isLoading"
                @click="combatZone.recallParty()"
              >
                <Icon icon="mdi:arrow-u-left-top" class="mr-1 size-4" />
                Recall contender
              </Button>
            </div>
          </div>

          <div
            v-else
            class="space-y-3 rounded border border-theme-primary/25 bg-surface-raised/40 p-4"
          >
            <div class="flex flex-wrap items-center justify-between gap-2">
              <p class="text-xs uppercase tracking-widest text-theme-primary/60">
                Send a contender
              </p>
              <p class="text-xs text-theme-primary/60">
                Entry fee <strong class="text-theme-primary">{{ fee ?? '—' }}</strong> caps
                <span v-if="caps !== null"> · Vault has {{ caps }}</span>
              </p>
            </div>

            <div v-if="eligibleDwellers.length" class="max-h-56 space-y-1 overflow-y-auto">
              <Button
                v-for="dweller in eligibleDwellers"
                :key="dweller.id"
                variant="outline"
                class="flex h-auto w-full items-center justify-between px-3 py-2 text-left text-xs"
                :class="
                  selectedDwellerId === dweller.id
                    ? 'border-theme-primary bg-theme-primary/10 text-theme-primary'
                    : 'border-theme-primary/20 text-theme-primary/70 hover:border-theme-primary/50'
                "
                @click="selectedDwellerId = dweller.id"
              >
                <span class="font-bold"
                  >{{ dweller.first_name }} {{ dweller.last_name ?? '' }}</span
                >
                <span>LVL {{ dweller.level }} · {{ dweller.status }}</span>
              </Button>
            </div>
            <p v-else class="text-xs text-theme-primary/60">
              No idle adult is available. Recall a contender or free a dweller from another
              assignment.
            </p>

            <Button :disabled="!canSend" size="sm" @click="send">
              <Icon icon="mdi:send" class="mr-1 size-4" />
              {{ combatZone.isLoading ? 'Posting the purse…' : 'Send to Interchange 77' }}
            </Button>
            <p class="text-[11px] text-theme-primary/45">
              One contender per vault. The purse is posted on send. The loser returns at 1 HP;
              nobody dies in the Zone.
            </p>
          </div>

          <div class="grid gap-2 text-xs text-theme-primary/65 sm:grid-cols-3">
            <p>
              <strong class="text-theme-primary">One contender.</strong> The Umpire registers one
              municipal unit per bout.
            </p>
            <p>
              <strong class="text-theme-primary">The purse is posted.</strong> No purse, no bell.
              The house keeps its fee.
            </p>
            <p>
              <strong class="text-theme-primary">No permanent injuries.</strong> The frequency sees
              everything; fleeing is a forfeiture.
            </p>
          </div>
        </section>

        <section v-else class="space-y-4">
          <div>
            <p class="text-xs uppercase tracking-widest text-theme-primary/60">
              Waiting at the bell
            </p>
            <ul v-if="combatZone.lobby?.queued.length" class="mt-2 space-y-2">
              <li
                v-for="queued in combatZone.lobby.queued"
                :key="queued.party_id"
                class="flex flex-wrap items-center justify-between gap-2 rounded border border-theme-primary/20 bg-surface-raised/40 px-3 py-2"
              >
                <div class="text-xs text-theme-primary/75">
                  <span class="font-bold text-theme-primary">Vault {{ queued.vault_number }}</span>
                  <span class="ml-2"
                    >LVL {{ queued.level }} · {{ Math.round(queued.power) }} power</span
                  >
                  <span class="ml-2 text-theme-primary/50"
                    >waiting {{ formatRemaining(queued.queued_seconds) }}</span
                  >
                </div>
                <Button
                  v-if="queued.vault_number !== myVaultNumber"
                  variant="outline"
                  size="sm"
                  :disabled="combatZone.isLoading || party?.status !== 'queued'"
                  @click="challenge(queued)"
                >
                  Challenge
                </Button>
              </li>
            </ul>
            <p v-else class="mt-2 text-xs text-theme-primary/60">
              The frequency is quiet. The tick will pair queued parties when a contender arrives.
            </p>
          </div>

          <div>
            <p class="text-xs uppercase tracking-widest text-theme-primary/60">Recent results</p>
            <ul v-if="combatZone.history.length" class="mt-2 space-y-2">
              <li
                v-for="entry in combatZone.history.slice(0, 5)"
                :key="entry.match_id"
                class="flex flex-wrap items-center justify-between gap-2 rounded border border-theme-primary/20 bg-surface-raised/40 px-3 py-2 text-xs text-theme-primary/75"
              >
                <span>
                  {{ entry.party_a.fighter.name }} vs {{ entry.party_b.fighter.name }} ·
                  {{ entry.finish_reason ?? 'completed' }} · {{ entry.pot_caps }} caps
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  @click="
                    replaying = true;
                    combatZone.watchMatch(entry.match_id)
                  "
                >
                  Replay
                </Button>
              </li>
            </ul>
            <p v-else class="mt-2 text-xs text-theme-primary/60">No bouts have settled yet.</p>
          </div>

          <div>
            <p class="text-xs uppercase tracking-widest text-theme-primary/60">Live bouts</p>
            <ul v-if="combatZone.lobby?.active_matches.length" class="mt-2 space-y-2">
              <li
                v-for="active in combatZone.lobby.active_matches"
                :key="active.match_id"
                class="flex flex-wrap items-center justify-between gap-2 rounded border border-theme-primary/20 bg-surface-raised/40 px-3 py-2 text-xs text-theme-primary/75"
              >
                <span>
                  Vault {{ active.vault_a_number }} vs Vault {{ active.vault_b_number }} · round
                  {{ active.round_seq }} · {{ active.pot_caps }} caps
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  @click="
                    replaying = false;
                    combatZone.watchMatch(active.match_id)
                  "
                >
                  Watch
                </Button>
              </li>
            </ul>
            <p v-else class="mt-2 text-xs text-theme-primary/60">
              No bout is live. The bell is waiting.
            </p>
          </div>
        </section>
      </template>
    </template>

    <template #footer>
      <Button variant="outline" size="sm" @click="closePanel">Close</Button>
    </template>
  </TerminalModal>
</template>
