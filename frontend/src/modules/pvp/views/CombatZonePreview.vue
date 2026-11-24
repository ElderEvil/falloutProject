<script setup lang="ts">
// Amber comes from the `--color-pit-amber` token in `tailwind.css`: pinned across themes
// because the fnv primary is theme-scoped and the exhibition keeps amber.
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { Icon } from '@iconify/vue'
import { Badge } from '@/core/components/ui/badge'
import { Button } from '@/core/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/core/components/ui/card'
import { Progress } from '@/core/components/ui/progress'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import { getDwellerDisplayName, type DwellerShort } from '@/modules/dwellers/models/dweller'
import { getDwellersByVault } from '@/modules/dwellers/services/dwellerService'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useVaultStore } from '@/modules/vault/stores/vault'

const PARTY_SIZE = 3
const SEAL_WINDOW_MS = 90_000
const BOARD_WINDOW_MS = 6 * 60 * 60 * 1000
const MAX_ROUNDS = 6
const ROUND_INTERVAL_MS = 900

type SideKey = 'vault' | 'opposition'
type Phase = 'sealed' | 'bout' | 'verdict'

interface Fighter {
  dweller: DwellerShort
  name: string
  maxHp: number
  special: string
}

interface JournalLine {
  key: number
  text: string
}

interface SideView {
  key: SideKey
  label: string
  sublabel: string
  fighters: Fighter[]
  hp: number[]
  fill: string
}

/** Coarse bands only: the board never publishes exact stats. */
const POWER_BANDS = [
  { label: 'Elite', min: 165 },
  { label: 'Hardened', min: 130 },
  { label: 'Seasoned', min: 95 },
  { label: 'Fledgling', min: 0 },
] as const

const { filter: dwellerFilter } = useDwellerStore()
const vaultStore = useVaultStore()

const oppositionRoster = ref<DwellerShort[]>([])
const nowMs = ref(Date.now())
const mountedAt = nowMs.value
const sealOpensAt = mountedAt + SEAL_WINDOW_MS
const boardExpiresAt = mountedAt + BOARD_WINDOW_MS

const phase = ref<Phase>('sealed')
const round = ref(0)
const journal = ref<JournalLine[]>([])
const ownHp = ref<number[]>([])
const oppositionHp = ref<number[]>([])
const winner = ref<SideKey | null>(null)

let clock: ReturnType<typeof setInterval> | null = null
let boutTimer: ReturnType<typeof setInterval> | null = null
let rng = 7
let journalKey = 0
/** Monotonic guard: a roster response older than the latest request (or bout) is dropped. */
let rosterSeq = 0

const rosterSettled = ref(false)
const vaultId = computed(() => vaultStore.currentVaultId)
const vaultNumber = computed(
  () =>
    vaultStore.activeVault?.number ??
    vaultStore.vaults.find((vault) => vault.id === vaultId.value)?.number ??
    null
)
const vaultLabel = computed(() =>
  vaultNumber.value === null ? 'Vault —' : `Vault ${String(vaultNumber.value).padStart(3, '0')}`
)

/** Same scoring the roster ranks by: combat power when present, level and SPECIAL always. */
function powerScore(dweller: DwellerShort): number {
  const special =
    dweller.strength +
    dweller.perception +
    dweller.endurance +
    dweller.charisma +
    dweller.intelligence +
    dweller.agility +
    dweller.luck
  return (dweller.combat_power ?? 0) + dweller.level * 4 + special
}

function bandFor(fighters: Fighter[]): string {
  if (!fighters.length) return 'Unrated'
  const average =
    fighters.reduce((total, fighter) => total + powerScore(fighter.dweller), 0) / fighters.length
  return POWER_BANDS.find((band) => average >= band.min)?.label ?? 'Unrated'
}

function toFighter(dweller: DwellerShort): Fighter {
  return {
    dweller,
    name: getDwellerDisplayName(dweller) || 'Unnamed dweller',
    maxHp: Math.max(1, dweller.effective_max_health || dweller.max_health),
    special: [
      dweller.strength,
      dweller.perception,
      dweller.endurance,
      dweller.charisma,
      dweller.intelligence,
      dweller.agility,
      dweller.luck,
    ]
      .map((value, index) => `${'SPECIAL'[index]}${value}`)
      .join(' '),
  }
}

const livingRoster = computed(() =>
  [...dwellerFilter.allDwellers].filter((dweller) => dweller.status !== 'dead')
)
const ranked = computed(() => [...livingRoster.value].sort((a, b) => powerScore(b) - powerScore(a)))

const ownTrio = computed(() => ranked.value.slice(0, PARTY_SIZE).map(toFighter))

/**
 * The opposing trio prefers the player's second vault (a real cross-vault duel).
 * The dweller store is vault-scoped and rejects off-vault reads, so the preview
 * reads the second roster through the same service without adopting it; with a
 * single vault the next three dwellers stand in and the seal card says so.
 */
const oppositionSource = computed(() => {
  const external = oppositionRoster.value.filter((dweller) => dweller.status !== 'dead')
  return external.length
    ? external.slice(0, PARTY_SIZE)
    : ranked.value.slice(PARTY_SIZE, PARTY_SIZE * 2)
})
const oppositionTrio = computed(() => oppositionSource.value.map(toFighter))
const oppositionIsSameVault = computed(
  () => oppositionRoster.value.filter((dweller) => dweller.status !== 'dead').length === 0
)
/** The label and the stand-in note share one resolved condition, dead dwellers included. */
const oppositionLabel = computed(() =>
  oppositionIsSameVault.value ? 'Stand-in trio' : 'Opposing vault'
)

const sides = computed<SideView[]>(() => [
  {
    key: 'vault',
    label: vaultLabel.value,
    sublabel: `${ownTrio.value.length} committed`,
    fighters: ownTrio.value,
    hp: ownHp.value,
    fill: 'var(--color-pit-amber)',
  },
  {
    key: 'opposition',
    label: oppositionLabel.value,
    sublabel: `${oppositionTrio.value.length} committed`,
    fighters: oppositionTrio.value,
    hp: oppositionHp.value,
    fill: 'var(--color-theme-primary)',
  },
])

const boardBand = computed(() => bandFor(ownTrio.value))
const oppositionBand = computed(() => bandFor(oppositionTrio.value))

const sealDigest = computed(() => {
  let hash = 0x811c9dc5
  for (const fighter of [...ownTrio.value, ...oppositionTrio.value]) {
    for (const char of `${fighter.dweller.id}${fighter.maxHp}`) {
      hash ^= char.charCodeAt(0)
      hash = Math.imul(hash, 0x01000193)
    }
  }
  return (hash >>> 0).toString(16).padStart(8, '0')
})

const sealRemainingMs = computed(() => Math.max(0, sealOpensAt - nowMs.value))
const gateOpen = computed(() => sealRemainingMs.value === 0)
const sealCountdown = computed(() => {
  const total = Math.ceil(sealRemainingMs.value / 1000)
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
})
const boardExpiry = computed(() => {
  const total = Math.max(0, boardExpiresAt - nowMs.value)
  return `${Math.floor(total / 3_600_000)}h ${String(Math.floor((total % 3_600_000) / 60_000)).padStart(2, '0')}m`
})
const postedAt = computed(() => new Date(mountedAt).toISOString().slice(11, 16))

const winnerLabel = computed(() => {
  if (!winner.value) return ''
  return winner.value === 'vault' ? vaultLabel.value : oppositionLabel.value
})
const verdictLine = computed(() => {
  if (!winner.value) return ''
  return winner.value === 'vault'
    ? 'Vault-Tec records the exhibition as a sanctioned win. Both trios are released to debrief.'
    : 'The challenger takes the pit. Vault-Tec thanks both trios for their voluntary participation.'
})

const canFight = computed(() => ownTrio.value.length > 0 && oppositionTrio.value.length > 0)
/** One instant drives both the countdown and the button: no gate/button drift. */
const takeBoutDisabled = computed(() => !canFight.value || !gateOpen.value)

function hpPercent(side: SideView, index: number): number {
  const fighter = side.fighters[index]
  if (!fighter) return 0
  const hp = side.hp[index] ?? fighter.maxHp
  return Math.round((hp / fighter.maxHp) * 100)
}

function nextRandom(): number {
  rng = (rng * 1_664_525 + 1_013_904_223) % 4_294_967_296
  return rng / 4_294_967_296
}

function pushJournal(text: string): void {
  journalKey += 1
  journal.value = [...journal.value, { key: journalKey, text }]
}

function stopBout(): void {
  if (boutTimer === null) return
  clearInterval(boutTimer)
  boutTimer = null
}

/** One volley per side, alternating, so both trios act inside the same round. */
function volley(
  attackers: Fighter[],
  attackerHp: number[],
  targets: Fighter[],
  targetHp: number[]
): void {
  attackers.forEach((attacker, index) => {
    if ((attackerHp[index] ?? 0) <= 0) return
    const alive = targetHp
      .map((hp, targetIndex) => (hp > 0 ? targetIndex : -1))
      .filter((i) => i >= 0)
    if (!alive.length) return
    const targetIndex = alive[Math.floor(nextRandom() * alive.length)]
    const target = targets[targetIndex]
    const damage = 6 + Math.floor(nextRandom() * 15)
    const remaining = Math.max(0, (targetHp[targetIndex] ?? 0) - damage)
    targetHp[targetIndex] = remaining
    pushJournal(
      remaining === 0
        ? `${attacker.name} drops ${target.name} — card spent`
        : `${attacker.name} hits ${target.name} for ${damage}`
    )
  })
}

function finishBout(): void {
  stopBout()
  const ratio = (hp: number[], fighters: Fighter[]) =>
    fighters.reduce(
      (total, fighter, index) => total + Math.max(0, hp[index] ?? 0) / fighter.maxHp,
      0
    )
  const ownRatio = ratio(ownHp.value, ownTrio.value)
  const oppositionRatio = ratio(oppositionHp.value, oppositionTrio.value)
  winner.value = ownRatio >= oppositionRatio ? 'vault' : 'opposition'
  phase.value = 'verdict'
  pushJournal(`rostrum — ${winnerLabel.value} takes the pit`)
}

function stepRound(): void {
  round.value += 1
  volley(ownTrio.value, ownHp.value, oppositionTrio.value, oppositionHp.value)
  volley(oppositionTrio.value, oppositionHp.value, ownTrio.value, ownHp.value)
  const wiped = (hp: number[]) => hp.every((value) => value <= 0)
  if (wiped(ownHp.value) || wiped(oppositionHp.value) || round.value >= MAX_ROUNDS) finishBout()
}

function startBout(): void {
  if (!canFight.value || !gateOpen.value) return
  // Any opposition fetch issued before the bell is stale: it must not swap the trio mid-bout.
  rosterSeq += 1
  stopBout()
  round.value = 0
  journal.value = []
  journalKey = 0
  winner.value = null
  ownHp.value = ownTrio.value.map((fighter) => fighter.maxHp)
  oppositionHp.value = oppositionTrio.value.map((fighter) => fighter.maxHp)
  rng = (Date.now() % 4_294_967_296) + 11
  phase.value = 'bout'
  pushJournal(`bell — ${vaultLabel.value} meets ${oppositionLabel.value} in the pit`)
  boutTimer = setInterval(stepRound, ROUND_INTERVAL_MS)
}

/** Reset the card whenever the rosters resolve, so the bars start full. */
function resetBout(): void {
  stopBout()
  phase.value = 'sealed'
  round.value = 0
  journal.value = []
  journalKey = 0
  winner.value = null
  ownHp.value = ownTrio.value.map((fighter) => fighter.maxHp)
  oppositionHp.value = oppositionTrio.value.map((fighter) => fighter.maxHp)
}

watch([ownTrio, oppositionTrio], resetBout, { immediate: true })

onMounted(async () => {
  clock = setInterval(() => {
    nowMs.value = Date.now()
  }, 1000)

  // A preview that can never finish loading is a lie: always settle the empty state.
  try {
    if (!vaultStore.vaults.length) await vaultStore.fetchVaults()
    const activeId = vaultId.value
    if (!activeId) return
    await dwellerFilter.fetchAllDwellers(activeId)

    const other = vaultStore.vaults.find((vault) => vault.id !== activeId)
    if (!other) return
    const seq = ++rosterSeq
    try {
      const fetched = await getDwellersByVault(other.id, { limit: PARTY_SIZE * 2 })
      if (seq === rosterSeq) oppositionRoster.value = fetched
    } catch {
      // A preview must still render: the reserve trio stands in for an unreachable vault.
      if (seq === rosterSeq) oppositionRoster.value = []
    }
  } finally {
    rosterSettled.value = true
  }
})

onUnmounted(() => {
  if (clock !== null) clearInterval(clock)
  clock = null
  stopBout()
})
</script>

<template>
  <main
    class="relative min-h-screen overflow-hidden bg-surface-canvas px-4 py-6 font-mono text-theme-primary sm:px-6 sm:py-10"
  >
    <img
      src="/dev/combat-zone/arena-backdrop.webp"
      alt=""
      aria-hidden="true"
      class="pointer-events-none absolute inset-x-0 top-0 h-[520px] w-full object-cover opacity-15"
    />
    <div class="relative mx-auto flex max-w-5xl flex-col gap-6">
      <header class="flex flex-col gap-3 border-b border-theme-primary/30 pb-4">
        <RouterLink to="/dev" class="w-fit text-sm underline underline-offset-4">
          Back to development tools
        </RouterLink>
        <p class="text-xs uppercase tracking-[0.2em] text-theme-primary/60">
          Vault-Tec sanctioned exhibition
        </p>
        <div class="flex flex-wrap items-center gap-3">
          <h1 class="text-2xl font-bold tracking-wide">The Pit</h1>
          <Badge variant="outline" class="border-pit-amber/60 text-pit-amber"
            >simulated bout — no server call</Badge
          >
        </div>
        <p class="max-w-2xl text-sm leading-relaxed text-theme-primary/80">
          Duel board, seal and bout as one console. Your trio comes from the live roster; the open
          challenge, seal clock and bout are client-side fixtures until the pvp module is wired.
        </p>
      </header>

      <div class="grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        <Card class="border-theme-primary/25 bg-surface/85">
          <CardHeader class="gap-2">
            <div class="flex items-start justify-between gap-3">
              <div class="space-y-1">
                <p class="text-xs uppercase tracking-[0.2em] text-theme-primary/60">Duel board</p>
                <CardTitle class="text-lg">Open challenge</CardTitle>
              </div>
              <Badge variant="outline" class="border-theme-primary/40 text-theme-primary/80">
                1 on the board
              </Badge>
            </div>
            <CardDescription>
              Posted {{ postedAt }} · any vault may answer before the seal closes.
            </CardDescription>
          </CardHeader>
          <CardContent class="flex flex-col gap-4">
            <dl class="grid grid-cols-2 gap-3 text-sm">
              <div class="rounded border border-theme-primary/20 bg-surface-sunken p-3">
                <dt class="text-xs uppercase tracking-widest text-theme-primary/60">Vault</dt>
                <dd class="mt-1 font-bold">{{ vaultLabel }}</dd>
              </div>
              <div class="rounded border border-theme-primary/20 bg-surface-sunken p-3">
                <dt class="text-xs uppercase tracking-widest text-theme-primary/60">Party</dt>
                <dd class="mt-1 font-bold">{{ ownTrio.length }} dwellers</dd>
              </div>
              <div class="rounded border border-theme-primary/20 bg-surface-sunken p-3">
                <dt class="text-xs uppercase tracking-widest text-theme-primary/60">Power band</dt>
                <dd class="mt-1 font-bold text-pit-amber">{{ boardBand }}</dd>
              </div>
              <div class="rounded border border-theme-primary/20 bg-surface-sunken p-3">
                <dt class="text-xs uppercase tracking-widest text-theme-primary/60">Expires</dt>
                <dd class="mt-1 font-bold tabular-nums">{{ boardExpiry }}</dd>
              </div>
            </dl>

            <ul class="flex flex-col gap-2">
              <li
                v-for="fighter in ownTrio"
                :key="fighter.dweller.id"
                class="flex items-center gap-3 rounded border border-theme-primary/20 bg-surface-canvas p-2"
                :title="fighter.special"
              >
                <DwellerPortrait
                  :thumbnail-url="fighter.dweller.thumbnail_url"
                  alt=""
                  fallback-icon="mdi:account-circle"
                  image-class="h-10 w-10 rounded object-cover"
                  fallback-class="h-10 w-10 text-theme-primary/60"
                />
                <div class="min-w-0 flex-1">
                  <p class="truncate text-sm font-bold">{{ fighter.name }}</p>
                  <p class="text-xs text-theme-primary/60">
                    Lv {{ fighter.dweller.level }} · {{ fighter.special }}
                  </p>
                </div>
                <Badge variant="outline" class="border-theme-primary/30 text-theme-primary/70">
                  {{ bandFor([fighter]) }}
                </Badge>
              </li>
              <li
                v-if="!ownTrio.length && !rosterSettled"
                class="rounded border border-dashed border-theme-primary/30 p-4 text-sm text-theme-primary/60"
              >
                Loading the vault roster…
              </li>
              <li
                v-else-if="!ownTrio.length"
                class="rounded border border-dashed border-theme-primary/30 p-4 text-sm text-theme-primary/60"
              >
                No roster to draw from. Select a vault, or seed dwellers, then reload this page.
              </li>
            </ul>
          </CardContent>
        </Card>

        <Card class="border-pit-amber/40 bg-surface/85">
          <CardHeader class="items-center gap-2 text-center">
            <img
              src="/dev/combat-zone/versus-crest.webp"
              alt=""
              aria-hidden="true"
              class="h-16 w-16 opacity-90"
            />
            <p class="text-xs uppercase tracking-[0.2em] text-theme-primary/60">Sealed card</p>
            <CardTitle class="text-lg">Both trios committed</CardTitle>
            <CardDescription>
              Result already drawn and sealed. The gate opens on the same tick for both vaults.
            </CardDescription>
          </CardHeader>
          <CardContent class="flex flex-col gap-4">
            <div class="grid grid-cols-[1fr_auto_1fr] items-center gap-3 text-sm">
              <div class="text-right">
                <p class="font-bold">{{ vaultLabel }}</p>
                <p class="text-xs text-theme-primary/60">{{ boardBand }} band</p>
              </div>
              <Icon icon="mdi:sword-cross" class="size-6 text-pit-amber" :ariaHidden="true" />
              <div>
                <p class="font-bold">{{ oppositionLabel }}</p>
                <p class="text-xs text-theme-primary/60">{{ oppositionBand }} band</p>
              </div>
            </div>

            <div class="rounded border border-theme-primary/20 bg-surface-sunken px-3 py-2 text-xs">
              <span class="text-theme-primary/60">sealed digest</span>
              <span class="ml-2 tabular-nums text-pit-amber">{{ sealDigest }}</span>
            </div>

            <div
              class="flex flex-col items-center gap-1 rounded border border-pit-amber/40 bg-surface-sunken py-4"
            >
              <p class="text-xs uppercase tracking-[0.25em] text-theme-primary/60">
                {{ gateOpen ? 'gate open' : 'gate opens in' }}
              </p>
              <p class="text-4xl font-bold tabular-nums text-pit-amber">
                {{ gateOpen ? '—:—' : sealCountdown }}
              </p>
              <p class="text-xs text-theme-primary/60">
                {{ gateOpen ? 'both vaults may now unseal' : 'same instant for both vaults' }}
              </p>
            </div>

            <Button
              v-if="phase === 'sealed'"
              class="w-full"
              :disabled="takeBoutDisabled"
              @click="startBout"
            >
              <Icon icon="mdi:sword" :ariaHidden="true" />
              Take the bout
            </Button>
            <p v-else class="text-center text-xs text-theme-primary/60">
              Bout card is live — see the bout panel.
            </p>
            <p v-if="!gateOpen && canFight" class="text-center text-xs text-theme-primary/60">
              The gate opens in {{ sealCountdown }} — both vaults unseal on the same tick.
            </p>

            <p
              v-if="rosterSettled && oppositionIsSameVault"
              class="text-xs leading-relaxed text-theme-primary/60"
            >
              No second vault on this account: the opposing trio is drawn from your own reserve and
              stands in for a real challenger.
            </p>
          </CardContent>
        </Card>
      </div>

      <Card class="relative overflow-hidden border-theme-primary/25 bg-surface/85">
        <CardHeader class="gap-2">
          <div class="flex items-start justify-between gap-3">
            <div class="space-y-1">
              <p class="text-xs uppercase tracking-[0.2em] text-theme-primary/60">Bout</p>
              <CardTitle class="text-lg">Exhibition card</CardTitle>
            </div>
            <div class="text-right">
              <p class="text-xs uppercase tracking-widest text-theme-primary/60">Round</p>
              <p class="text-2xl font-bold tabular-nums text-pit-amber">
                {{ phase === 'sealed' ? '—' : String(round).padStart(2, '0') }}
              </p>
            </div>
          </div>
          <CardDescription>
            Segmented health per dweller. The journal below is the simulated feed.
          </CardDescription>
        </CardHeader>

        <CardContent class="relative z-10 grid gap-6 md:grid-cols-2">
          <section v-for="side in sides" :key="side.key" class="flex flex-col gap-3">
            <div
              class="flex items-baseline justify-between gap-2 border-b border-theme-primary/20 pb-1"
            >
              <h3 class="text-sm font-bold uppercase tracking-widest">{{ side.label }}</h3>
              <span class="text-xs text-theme-primary/60">{{ side.sublabel }}</span>
            </div>
            <ul class="flex flex-col gap-3">
              <li
                v-for="(fighter, index) in side.fighters"
                :key="`${side.key}-${fighter.dweller.id}-${index}`"
                class="flex items-center gap-3"
              >
                <DwellerPortrait
                  :thumbnail-url="fighter.dweller.thumbnail_url"
                  alt=""
                  fallback-icon="mdi:account-circle"
                  image-class="h-8 w-8 rounded object-cover"
                  fallback-class="h-8 w-8 text-theme-primary/60"
                />
                <div class="min-w-0 flex-1">
                  <div class="flex items-baseline justify-between gap-2 text-xs">
                    <span class="truncate font-bold">{{ fighter.name }}</span>
                    <span class="shrink-0 tabular-nums text-theme-primary/60">
                      {{ side.hp[index] ?? fighter.maxHp }}/{{ fighter.maxHp }}
                    </span>
                  </div>
                  <Progress
                    class="mt-1"
                    :model-value="hpPercent(side, index)"
                    :fill="side.fill"
                    size="md"
                    segmented
                    :label="`${fighter.name} condition`"
                    :value-text="`${hpPercent(side, index)} percent`"
                  />
                </div>
              </li>
              <li v-if="!side.fighters.length" class="text-xs text-theme-primary/60">
                No dweller available for this side.
              </li>
            </ul>
          </section>
        </CardContent>

        <CardContent class="relative z-10 flex flex-col gap-3">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <h3 class="text-xs uppercase tracking-[0.25em] text-theme-primary/60">Journal</h3>
            <span class="text-xs text-theme-primary/50">simulated feed — no server call</span>
          </div>
          <ol
            class="max-h-56 overflow-y-auto rounded border border-theme-primary/20 bg-surface-sunken p-3 text-xs leading-relaxed"
            aria-live="polite"
          >
            <li v-for="(line, index) in journal" :key="line.key" class="flex gap-2">
              <span class="shrink-0 text-theme-primary/40 tabular-nums">
                {{ String(index + 1).padStart(2, '0') }}
              </span>
              <span>{{ line.text }}</span>
            </li>
            <li v-if="!journal.length" class="text-theme-primary/50">
              Awaiting the bell. The feed is simulated and never calls the API.
            </li>
          </ol>
        </CardContent>

        <CardContent v-if="phase === 'verdict'" class="relative z-10">
          <div class="flex flex-col gap-3 rounded border border-pit-amber/60 bg-surface-sunken p-4">
            <p class="text-xs uppercase tracking-[0.25em] text-theme-primary/60">Verdict</p>
            <p class="text-xl font-bold text-pit-amber">{{ winnerLabel }} takes the pit</p>
            <p class="text-sm leading-relaxed text-theme-primary/80">{{ verdictLine }}</p>
            <Button variant="outline" size="sm" class="w-fit" @click="startBout">
              <Icon icon="mdi:replay" :ariaHidden="true" />
              Run again
            </Button>
          </div>
        </CardContent>

        <img
          src="/dev/combat-zone/crowd-silhouette.webp"
          alt=""
          aria-hidden="true"
          class="pointer-events-none absolute inset-x-0 bottom-0 h-24 w-full object-cover opacity-20"
        />
      </Card>
    </div>
  </main>
</template>
