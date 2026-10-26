<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import { Progress } from '@/core/components/ui/progress'
import TerminalModal from '@/core/components/common/TerminalModal.vue'
import TerminalModalActions from '@/core/components/common/TerminalModalActions.vue'
import ExpeditionOutcomeLines from './ExpeditionOutcomeLines.vue'
import WastelandScene from './WastelandScene.vue'
import SiteCombatScene from './SiteCombatScene.vue'
import BattleLog from '@/modules/rooms/components/BattleLog.vue'
import type { BattleLogEntry } from '@/modules/rooms/models/battleLog'
import { isTerminal, useExpeditionSiteStore } from '../stores/expeditionSite'

interface Props {
  show: boolean
  explorationId: string
  dwellerName?: string
  dwellerImageUrl?: string | null
  dwellerThumbnailUrl?: string | null
  explorationActive?: boolean
  reportedSiteId?: string
  pausesTravel?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  dwellerName: '',
  dwellerImageUrl: null,
  dwellerThumbnailUrl: null,
  explorationActive: true,
  reportedSiteId: undefined,
  pausesTravel: false,
})

const emit = defineEmits<{
  close: []
  updated: []
}>()

const store = useExpeditionSiteStore()
const confirmingRetreat = ref(false)
const closing = ref(false)
const fighting = ref(false)
const combatPlaying = ref(false)
const queuedSkill = ref(false)
const combatExpanded = ref(false)

// Gap 4.3: never render a room that belongs to a different exploration.
const room = computed(() => {
  const current = store.room
  if (!current) return null
  return current.exploration_id === props.explorationId ? current : null
})
const hasOutcome = computed(() => !!room.value?.outcome)
const isTerminalRun = computed(() => (room.value ? isTerminal(room.value.status) : false))
const isDefeated = computed(() => !!room.value?.defeated && !isTerminalRun.value)
// Gap 1.6: a run left open on a non-active exploration is close-only.
const isRecovery = computed(() => !props.explorationActive && !!room.value)
const isCombatRoom = computed(() => room.value?.node.kind === 'combat')
const hasArenaCombat = computed(() => !!room.value?.combat_state)
const expandedCombat = computed(
  () => hasArenaCombat.value && (combatExpanded.value || (room.value?.combat_state?.round ?? 0) > 0)
)

const startCombat = () => {
  combatExpanded.value = true
  fighting.value = true
}

watch(
  () => props.explorationId,
  () => {
    fighting.value = false
    combatExpanded.value = false
    queuedSkill.value = false
  }
)

// Player-started combat pauses when the modal closes. Reconnect shows persisted HP/turns.
watch(
  () => [
    props.show,
    fighting.value,
    combatPlaying.value,
    store.isLoading,
    room.value?.combat_state?.round,
    room.value?.status,
  ],
  (_, __, onCleanup) => {
    if (
      !props.show ||
      !fighting.value ||
      combatPlaying.value ||
      store.isLoading ||
      room.value?.status !== 'in_room'
    )
      return
    const timer = setTimeout(async () => {
      const useSkill = queuedSkill.value && room.value?.combat_state?.next_attack_team === 'A'
      if (useSkill) queuedSkill.value = false
      await store.resolveNode(props.explorationId, undefined, useSkill).catch(() => {
        fighting.value = false
      })
    }, 1100)
    onCleanup(() => clearTimeout(timer))
  },
  { flush: 'post' }
)
// Dedupe the room's enemy roster so duplicates read as counts, not a repeated list.
const enemySummary = computed(() => {
  const names = room.value?.node.enemy_names ?? []
  const counts = new Map<string, number>()
  for (const name of names) counts.set(name, (counts.get(name) ?? 0) + 1)
  return [...counts.entries()].map(([name, n]) => (n > 1 ? `${name} ×${n}` : name)).join(', ')
})

// Per-enemy engagement results, in fight order (present only after a resolve).
const combatOutcome = computed(() => room.value?.outcome?.combat ?? [])
const journalEntries = computed<BattleLogEntry[]>(() =>
  (room.value?.combat_state?.events ?? []).map((event) => ({
    id: event.id,
    kind: event.action?.skill ? 'SKILL' : event.action ? 'HIT' : 'TURN',
    message: event.message,
    meta: event.id.includes(':') ? `Turn ${event.id.split(':')[0]}` : null,
    skillIcon: event.action?.skill_icon,
  }))
)

// Dweller HP readout in the header. Hidden when the backend reports no max health.
const showHealthBar = computed(() => (room.value?.dweller_max_health ?? 0) > 0)
const healthRatio = computed(() => {
  const max = room.value?.dweller_max_health ?? 0
  if (max <= 0) return 0
  return Math.min(1, (room.value?.dweller_health ?? 0) / max)
})
const healthPercent = computed(() => Math.round(healthRatio.value * 100))
const healthTone = computed<'default' | 'warning' | 'danger'>(() => {
  if (healthRatio.value < 0.3) return 'danger'
  if (healthRatio.value < 0.6) return 'warning'
  return 'default'
})
const healthToneText = computed(() => {
  switch (healthTone.value) {
    case 'danger':
      return 'text-danger'
    case 'warning':
      return 'text-warning'
    default:
      return 'text-theme-primary'
  }
})
// Brief "-N" flash on the HP bar whenever a resolve lands damage.
const damageFlash = ref<number | null>(null)
let damageFlashTimer: ReturnType<typeof setTimeout> | undefined

watch(
  () => room.value?.outcome,
  (outcome) => {
    if (outcome && outcome.damage_taken > 0) {
      damageFlash.value = outcome.damage_taken
      clearTimeout(damageFlashTimer)
      damageFlashTimer = setTimeout(() => {
        damageFlash.value = null
      }, 1600)
    }
  },
  { immediate: true }
)

onUnmounted(() => clearTimeout(damageFlashTimer))

watch(
  () => props.show,
  (isVisible, wasVisible) => {
    if (isVisible && !wasVisible) {
      closing.value = false
      confirmingRetreat.value = false
      fighting.value = false
      combatExpanded.value = false
      queuedSkill.value = false
      // Reconnect: a room already in the store (or fetched by the view) wins
      // over the picker; otherwise load the available sites fresh.
      if (!room.value && props.explorationActive) {
        store.fetchAvailableSites(props.explorationId).catch(() => {})
      }
    }
  },
  { immediate: true }
)

const handleEnter = (siteId: string) => {
  store.enterSite(props.explorationId, siteId).catch(() => {})
}

const handleResolve = (choiceId?: string) => {
  store.resolveNode(props.explorationId, choiceId).catch(() => {})
}

const handleRetreat = () => {
  fighting.value = false
  store.retreat(props.explorationId).catch(() => {})
}

const closeRun = (updated: boolean) => {
  if (closing.value) return
  closing.value = true
  store.reset()
  emit('close')
  if (updated) emit('updated')
}

const handleTerminalClose = () => closeRun(true)
const handleRecoveryClose = () => closeRun(false)

const handleDialogClose = () => {
  if (closing.value) return
  if (isRecovery.value) {
    handleRecoveryClose()
  } else if (room.value && isTerminal(room.value.status)) {
    handleTerminalClose()
  } else {
    emit('close')
  }
}

const successOdds = (odds: number): string => `${Math.round(odds * 100)}%`

const outcomeLines = computed(() => {
  const outcome = room.value?.outcome
  if (!outcome) return []
  const lines: string[] = []
  if (outcome.damage_taken > 0) lines.push(`${outcome.damage_taken} damage taken`)
  if (outcome.caps_gained > 0) lines.push(`+${outcome.caps_gained} caps`)
  if (outcome.loot_gained && outcome.loot_gained.length > 0)
    lines.push(outcome.loot_gained.join(', '))
  return lines
})

const terminalBanner = computed(() => {
  if (!room.value) return null
  switch (room.value.status) {
    case 'cleared':
      return {
        icon: 'mdi:check-decagram',
        text: 'Site cleared — rewards added to the expedition haul.',
        classes: 'border-theme-primary/40 bg-theme-primary/10 text-theme-primary',
      }
    case 'retreated':
      return {
        icon: 'mdi:arrow-u-left-top',
        text: 'Retreated with whatever was carried.',
        classes: 'border-warning/40 bg-warning/10 text-warning',
      }
    case 'defeated':
      return {
        icon: 'mdi:shield-alert-outline',
        text: 'Escaped injured — no site loot collected. Travel has resumed.',
        classes: 'border-warning/40 bg-warning/10 text-warning',
      }
    case 'died':
      return {
        icon: 'mdi:skull',
        text: 'The dweller died in the site.',
        classes: 'border-danger/40 bg-danger/10 text-danger',
      }
    default:
      return null
  }
})
</script>

<template>
  <TerminalModal
    :open="show"
    :title="room ? room.site_name : 'Expedition Site'"
    icon="mdi:radio-tower"
    icon-class="inline h-6 w-6 shrink-0 text-theme-primary"
    :size="expandedCombat ? 'screen' : '3xl'"
    :content-class="expandedCombat ? 'h-[calc(100dvh-2rem)] max-h-[calc(100dvh-2rem)]' : undefined"
    max-height="90"
    header-class="flex flex-shrink-0 flex-row items-center gap-2 border-b border-theme-primary/25 bg-theme-primary/5 pt-6 pr-14 pb-4 pl-6"
    @close="handleDialogClose"
  >
    <div
      v-if="room && !expandedCombat && !isTerminalRun && !isRecovery"
      aria-label="Encounter status"
      class="grid shrink-0 grid-cols-2 items-center gap-x-5 gap-y-3 border-b border-theme-primary/25 bg-surface-sunken/40 px-5 py-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)_auto]"
    >
      <div v-if="showHealthBar" class="flex min-w-0 flex-col gap-1.5">
        <span class="truncate text-xs text-theme-primary/70">{{ dwellerName || 'Dweller' }}</span>
        <div class="flex items-center gap-2">
          <span
            class="shrink-0 whitespace-nowrap text-[0.6875rem] font-semibold"
            :class="healthToneText"
          >
            HP {{ room.dweller_health }}/{{ room.dweller_max_health }}
          </span>
          <Progress
            :model-value="healthPercent"
            size="xs"
            :tone="healthTone"
            class="w-16 min-w-0 flex-1"
            :label="`Dweller health ${room.dweller_health}/${room.dweller_max_health}`"
            :value-text="`${healthPercent}%`"
          />
          <span
            v-if="damageFlash !== null"
            class="damage-flash text-[0.6875rem] font-bold text-danger"
            aria-hidden="true"
          >
            -{{ damageFlash }}
          </span>
        </div>
      </div>
      <div v-if="enemySummary && isCombatRoom" class="min-w-0" aria-label="Encounter enemies">
        <p class="mb-1 text-xs text-theme-primary/70">Hostiles</p>
        <p class="flex items-start gap-1.5 text-sm font-semibold text-danger">
          <Icon icon="mdi:sword-cross" class="mt-0.5 size-4 shrink-0" />
          <span>{{ enemySummary }}</span>
        </p>
      </div>
      <p class="col-span-2 flex items-center gap-1 text-xs text-theme-primary/70 sm:col-span-1">
        <Icon
          :icon="pausesTravel ? 'mdi:pause-circle-outline' : 'mdi:walk'"
          class="mr-1 inline size-4"
        />
        {{ pausesTravel ? 'Travel paused' : 'Travel continues' }}
      </p>
    </div>

    <div
      class="min-h-0 flex-1 px-5 pt-5 pb-5"
      :class="expandedCombat ? 'overflow-hidden' : 'overflow-y-auto'"
    >
      <!-- PICKER: no active run -->
      <template v-if="!room">
        <p class="mb-4 text-sm text-theme-primary/70">
          Enter before the dweller arrives home, including during the return trip.
          <template v-if="pausesTravel">Travel pauses while you play.</template>
        </p>
        <p
          v-if="
            reportedSiteId &&
            (!explorationActive ||
              (!store.isLoading &&
                !store.error &&
                !store.availableSites.some((site) => site.id === reportedSiteId)))
          "
          class="mb-4 rounded-md border border-warning/40 bg-warning/10 p-3 text-sm text-warning"
        >
          This site report is no longer available. The site may be cleared or the journey finished.
        </p>
        <p
          v-if="
            dwellerName &&
            explorationActive &&
            !store.isLoading &&
            !store.error &&
            store.availableSites.length
          "
          class="mb-4 text-sm text-theme-primary/70"
        >
          {{ dwellerName }} discovered
          {{ store.availableSites.length === 1 ? 'a site' : 'these sites' }}.
        </p>

        <p v-if="!explorationActive" class="py-6 text-center text-sm text-theme-primary/70">
          This journey has finished. Site offers have expired.
        </p>

        <div
          v-else-if="store.isLoading"
          class="flex flex-col items-center gap-3 py-10 text-theme-primary/70"
        >
          <Icon icon="mdi:loading" class="h-8 w-8 animate-spin" />
          <p class="text-sm">Scanning the wasteland…</p>
        </div>

        <div
          v-else-if="store.error"
          class="mb-4 rounded-md border border-danger/40 bg-danger/10 p-3 text-sm text-danger"
        >
          {{ store.error }}
        </div>

        <div
          v-else-if="store.availableSites.length === 0"
          class="flex flex-col items-center gap-3 py-10 text-theme-primary/60"
        >
          <Icon icon="mdi:map-marker-off" class="h-10 w-10" />
          <p class="text-center text-sm">No sites available on this journey.</p>
        </div>

        <div
          v-else
          class="grid gap-4"
          :class="{ 'sm:grid-cols-2': store.availableSites.length > 1 }"
        >
          <div
            v-for="site in store.availableSites"
            :key="site.id"
            class="rounded-md border-2 border-theme-primary/30 bg-surface-sunken p-4 transition-colors duration-200 hover:border-theme-primary/60"
            :class="{ 'ring-2 ring-theme-primary': site.id === reportedSiteId }"
          >
            <WastelandScene
              v-if="site.scene_id"
              class="mb-3 [&>div]:aspect-auto [&>div]:h-[min(22dvh,12rem)] [&>figcaption]:hidden [&_img]:object-cover"
              :scene="site.scene_id"
              variant="battleback"
              :heading="site.name"
              compact
            />
            <div class="mb-2 flex items-start justify-between gap-3">
              <h4 class="text-base font-bold text-theme-primary">
                {{ site.name }}
              </h4>
              <Button
                size="sm"
                :disabled="store.isLoading || !explorationActive"
                @click="handleEnter(site.id)"
              >
                <Icon icon="mdi:login" class="h-4 w-4" />
                Enter
              </Button>
            </div>
            <p class="mb-3 text-sm leading-relaxed text-theme-primary/80">{{ site.flavor }}</p>
            <p v-if="site.enemy_names?.length" class="mb-2 text-xs text-warning">
              Hostiles: {{ site.enemy_names.join(', ') }}
            </p>
            <p v-if="site.threat" class="mb-3 text-xs text-theme-primary/70">
              Estimated threat: {{ site.threat }}
            </p>
            <div class="flex flex-wrap gap-2">
              <span
                class="inline-flex items-center gap-1 rounded-[3px] border border-theme-primary/40 bg-theme-primary/10 px-1.5 py-0.5 text-[0.75rem] font-semibold text-theme-primary"
              >
                <Icon icon="mdi:account-star" class="h-3.5 w-3.5" />
                Lv {{ site.min_dweller_level }}
              </span>
              <span
                class="inline-flex items-center gap-1 rounded-[3px] border border-theme-primary/40 bg-theme-primary/10 px-1.5 py-0.5 text-[0.75rem] font-semibold text-theme-primary"
              >
                <Icon icon="mdi:door" class="h-3.5 w-3.5" />
                {{ site.room_total === 1 ? 'One encounter' : `${site.room_total} rooms` }}
              </span>
            </div>
          </div>
        </div>
      </template>

      <!-- ACTIVE RUN -->
      <div
        v-else
        class="grid gap-5"
        :class="
          expandedCombat
            ? 'h-full min-h-0 grid-rows-[minmax(0,1fr)_auto] md:grid-cols-[minmax(0,1fr)_20rem] xl:grid-cols-[minmax(0,1fr)_22rem] md:grid-rows-1'
            : 'items-start md:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]'
        "
      >
        <div class="min-w-0" :class="expandedCombat ? 'h-full min-h-0' : 'lg:sticky lg:top-0'">
          <SiteCombatScene
            v-if="expandedCombat"
            :room="room"
            :running="fighting"
            :loading="store.isLoading || queuedSkill"
            @playing="combatPlaying = $event"
            @skill="queuedSkill = true"
          />
          <WastelandScene
            v-else
            :scene="room.scene_id"
            variant="battleback"
            :heading="room.site_name"
            :description="hasArenaCombat ? undefined : room.flavor"
            :dweller-name="dwellerName"
            :image-url="dwellerImageUrl"
            :thumbnail-url="dwellerThumbnailUrl"
            :pet="room.combat_state?.fighters[0]?.pet"
          />
        </div>
        <div
          class="min-w-0"
          :class="
            expandedCombat
              ? 'flex min-h-0 max-h-[35dvh] flex-col overflow-y-auto md:h-full md:max-h-none'
              : undefined
          "
        >
          <section
            v-if="expandedCombat"
            aria-label="Battle journal"
            class="mb-4 flex min-h-0 flex-1 flex-col"
          >
            <h3 class="mb-2 text-sm font-semibold text-theme-primary">
              Battle journal · {{ journalEntries.length }} entries
            </h3>
            <BattleLog fill :entries="journalEntries" empty-text="No attacks yet." />
          </section>
          <details
            v-if="expandedCombat"
            class="mb-4 shrink-0 border-t border-theme-primary/25 pt-2 text-sm text-theme-primary/70"
          >
            <summary class="cursor-pointer py-1 focus-visible:outline focus-visible:outline-ring">
              Encounter briefing
            </summary>
            <p class="mt-2 leading-relaxed">{{ room.flavor }}</p>
            <p v-if="room.lore" class="mt-2 italic leading-relaxed">{{ room.lore }}</p>
          </details>
          <section
            v-if="hasArenaCombat && !expandedCombat"
            class="mb-4"
            aria-label="Encounter briefing"
          >
            <h3 class="mb-2 text-xs font-semibold uppercase tracking-widest text-theme-primary/60">
              Field report
            </h3>
            <p class="text-sm leading-relaxed text-theme-primary/90">{{ room.flavor }}</p>
          </section>
          <p
            v-if="room.lore && !expandedCombat"
            class="mb-4 border-l-2 border-theme-primary/25 pl-3 text-sm italic leading-relaxed text-theme-primary/70"
          >
            {{ room.lore }}
          </p>
          <div v-if="room.room_total > 1" class="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1">
            <span
              class="inline-flex items-center gap-1 rounded-[3px] border border-theme-primary/40 bg-theme-primary/10 px-1.5 py-0.5 text-[0.75rem] font-semibold text-theme-primary"
            >
              <Icon icon="mdi:map-marker-path" class="h-3.5 w-3.5" />
              Room {{ room.room_index + 1 }} / {{ room.room_total }}
            </span>
            <span class="text-lg font-bold text-theme-primary">{{ room.room_name }}</span>
          </div>

          <!-- RECOVERY: run open on a non-active exploration (Gap 1.6) -->
          <div
            v-if="isRecovery"
            class="mb-4 flex items-start gap-2 rounded-md border border-warning/40 bg-warning/10 p-3 text-sm font-semibold text-warning"
          >
            <Icon icon="mdi:clock-alert-outline" class="mt-0.5 h-5 w-5 shrink-0" />
            <span>This expedition has ended — the site run is closed.</span>
          </div>

          <!-- Outcome readout (the defeat banner carries its own copy) -->
          <div
            v-if="hasOutcome && !isDefeated && !combatPlaying && (!hasArenaCombat || isTerminalRun)"
            class="mb-4 rounded-md border border-theme-primary/30 bg-surface-sunken p-4 text-sm leading-relaxed text-theme-primary/90"
          >
            <p>{{ room.outcome?.text }}</p>
            <ExpeditionOutcomeLines :lines="outcomeLines" />
          </div>

          <ul
            v-if="combatOutcome.length > 0"
            class="mb-4 flex flex-col gap-1.5 rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-sm font-semibold"
            aria-label="Fight results"
          >
            <li
              v-for="(entry, index) in combatOutcome"
              :key="index"
              class="flex items-center gap-2"
            >
              <Icon
                :icon="entry.victory ? 'mdi:skull-outline' : 'mdi:sword-cross'"
                class="h-4 w-4 shrink-0"
                :class="entry.victory ? 'text-theme-primary/50' : 'text-danger'"
              />
              <span
                class="text-sm font-semibold"
                :class="entry.victory ? 'text-theme-primary/50 line-through' : 'text-danger'"
              >
                {{ entry.enemy }}
              </span>
              <span
                class="text-[0.75rem] font-semibold"
                :class="entry.victory ? 'text-theme-primary/50' : 'text-danger'"
              >
                {{ entry.victory ? 'defeated' : 'overpowered' }}
              </span>
              <span
                v-if="entry.damage_taken > 0"
                class="ml-auto text-[0.75rem] font-bold text-danger"
              >
                -{{ entry.damage_taken }}
              </span>
            </li>
          </ul>

          <!-- Terminal banner (terminal runs, incl. recovery) -->
          <div
            v-if="terminalBanner && !combatPlaying"
            class="mb-4 flex items-start gap-2 rounded-md border p-3 text-sm font-bold"
            :class="terminalBanner.classes"
          >
            <Icon :icon="terminalBanner.icon" class="mt-0.5 h-5 w-5 shrink-0" />
            <span>{{ terminalBanner.text }}</span>
          </div>

          <!-- ACTIVE ROOM: live actions only -->
          <template v-if="!isTerminalRun && !isRecovery">
            <!-- Room-pane error (Gap 4.2): visible where the failed action happened -->
            <div
              v-if="store.error"
              class="mb-4 rounded-md border border-danger/40 bg-danger/10 p-3 text-sm text-danger"
            >
              {{ store.error }}
            </div>

            <!-- Defeat banner (Gap 3) -->
            <div
              v-if="isDefeated"
              class="mb-4 rounded-md border border-danger/40 bg-danger/10 p-4 text-sm leading-relaxed text-danger"
            >
              <p class="mb-1 flex items-center gap-2 font-bold">
                <Icon icon="mdi:skull-crossbones" class="h-5 w-5" />
                Defeated
              </p>
              <p>{{ room.outcome?.text }}</p>
              <ExpeditionOutcomeLines :lines="outcomeLines" subdued />
            </div>

            <p v-if="!hasArenaCombat" class="mb-4 text-base font-semibold text-theme-primary">
              {{ room.node.prompt }}
            </p>
            <p v-else-if="!expandedCombat" class="mb-4 text-sm text-theme-primary/70">
              {{
                fighting
                  ? 'Combat is underway. Activate your weapon skill when its meter fills.'
                  : 'Start combat when ready. You can retreat during the fight.'
              }}
            </p>

            <div
              v-if="enemySummary && !expandedCombat && !isCombatRoom"
              class="mb-4 rounded-md border border-warning/40 bg-warning/10 px-3 py-2 text-sm font-semibold text-warning"
            >
              <div class="flex items-center gap-2">
                <Icon icon="mdi:alert-outline" class="h-4 w-4" />
                <span>If it goes wrong: {{ enemySummary }}</span>
              </div>
            </div>

            <!-- Choices resolve in this same scene. Fight/search actions stay in the footer. -->
            <template v-if="!isDefeated">
              <div
                v-if="room.node.options && room.node.options.length > 0"
                class="flex flex-col gap-2"
              >
                <Button
                  v-for="option in room.node.options"
                  :key="option.id"
                  class="justify-between gap-2 border-theme-primary/40 bg-theme-primary/10 text-left text-theme-primary hover:bg-theme-primary/20"
                  variant="outline"
                  size="lg"
                  :disabled="store.isLoading"
                  @click="handleResolve(option.id)"
                >
                  <span class="flex-1">{{ option.label }}</span>
                  <span
                    class="inline-flex items-center gap-1 rounded-[3px] border border-theme-primary/40 bg-surface-sunken px-1.5 py-0.5 text-[0.75rem] font-semibold"
                  >
                    <Icon icon="mdi:brain" class="h-3.5 w-3.5" />
                    {{ option.stat }}
                  </span>
                  <span
                    class="inline-flex items-center gap-1 rounded-[3px] border border-theme-primary/40 bg-surface-sunken px-1.5 py-0.5 text-[0.75rem] font-semibold"
                  >
                    <Icon icon="mdi:percent" class="h-3.5 w-3.5" />
                    {{ successOdds(option.success_odds) }}
                  </span>
                </Button>
              </div>
            </template>
          </template>
        </div>
      </div>
    </div>

    <template #footer>
      <slot name="footer">
        <!-- PICKER footer -->
        <Button v-if="!room" variant="secondary" size="lg" @click="emit('close')">
          <Icon icon="mdi:close" class="h-5 w-5" />
          Cancel
        </Button>

        <!-- RECOVERY footer: close-only (Gap 1.6) -->
        <Button v-else-if="isRecovery" class="w-full" size="lg" @click="handleRecoveryClose">
          <Icon icon="mdi:check-bold" class="h-5 w-5" />
          Close
        </Button>

        <!-- TERMINAL footer -->
        <Button
          v-else-if="isTerminalRun"
          class="w-full"
          size="lg"
          :disabled="combatPlaying"
          @click="handleTerminalClose"
        >
          <Icon icon="mdi:check-bold" class="h-5 w-5" />
          {{ room.room_total === 1 ? 'Return to journey' : 'Close' }}
        </Button>

        <!-- ROOM footer: retreat with confirm step -->
        <template v-else>
          <div v-if="confirmingRetreat" class="flex w-full flex-col items-end gap-2">
            <p class="flex items-center gap-1.5 text-xs font-semibold text-warning">
              <Icon icon="mdi:map-marker-path" class="h-3.5 w-3.5" />
              Retreating keeps this encounter open — you can return while the journey lasts.
            </p>
            <TerminalModalActions
              cancel-label="Keep Exploring"
              confirm-label="Retreat"
              confirm-icon="mdi:arrow-u-left-top"
              :confirm-disabled="store.isLoading"
              @cancel="confirmingRetreat = false"
              @confirm="handleRetreat"
            />
          </div>
          <div v-else class="flex w-full items-center gap-3">
            <Button
              v-if="isDefeated || !room.node.options?.length"
              class="flex-1"
              size="lg"
              :disabled="store.isLoading || fighting"
              @click="hasArenaCombat ? startCombat() : handleResolve()"
            >
              <Icon
                :icon="isCombatRoom || isDefeated ? 'mdi:sword-cross' : 'mdi:package-variant'"
                class="size-5"
              />
              {{
                hasArenaCombat && fighting
                  ? 'Fighting…'
                  : isDefeated
                    ? 'Push on'
                    : isCombatRoom
                      ? 'Fight'
                      : room.node.kind === 'finale'
                        ? 'Collect supplies'
                        : 'Continue'
              }}
            </Button>
            <Button
              v-if="room.can_retreat"
              class="ml-auto"
              variant="secondary"
              size="lg"
              :disabled="store.isLoading"
              @click="confirmingRetreat = true"
            >
              <Icon icon="mdi:arrow-u-left-top" class="size-5" />
              Retreat
            </Button>
          </div>
        </template>
      </slot>
    </template>
  </TerminalModal>
</template>

<style scoped>
/* Brief "-N" damage flash on the dweller HP bar: rises and fades out. */
.damage-flash {
  animation: damage-flash 1.6s ease-out forwards;
}

@keyframes damage-flash {
  0% {
    opacity: 0;
    transform: translateY(2px);
  }
  15% {
    opacity: 1;
  }
  70% {
    opacity: 1;
  }
  100% {
    opacity: 0;
    transform: translateY(-6px);
  }
}
</style>
